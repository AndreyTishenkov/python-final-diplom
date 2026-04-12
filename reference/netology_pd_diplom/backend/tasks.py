import os
import json
import csv
from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from celery import shared_task
from backend.models import ProductInfo, User
import yaml


@shared_task
def async_export_products(user_id, export_format='json', filters=None):
    """
    Асинхронная задача для экспорта товаров

    Args:
        user_id: ID пользователя, запросившего экспорт
        export_format: Формат экспорта (json, yaml, csv)
        filters: Словарь с параметрами фильтрации

    Returns:
        dict: Информация о результате экспорта
    """
    if filters is None:
        filters = {}

    try:
        # Получаем пользователя
        user = User.objects.get(id=user_id)

        # Формируем queryset с учетом прав пользователя
        if user.type == 'shop':
            # Магазин видит только свои товары
            queryset = ProductInfo.objects.filter(shop__user_id=user_id)
        else:
            # Публичный экспорт - только активные магазины
            queryset = ProductInfo.objects.filter(shop__state=True)

        # Применяем фильтры
        shop_id = filters.get('shop_id')
        category_id = filters.get('category_id')
        min_price = filters.get('min_price')
        max_price = filters.get('max_price')
        in_stock = filters.get('in_stock')

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        if category_id:
            queryset = queryset.filter(product__category_id=category_id)

        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        if in_stock and in_stock.lower() == 'true':
            queryset = queryset.filter(quantity__gt=0)

        # Подготавливаем данные для экспорта
        data = []
        for product in queryset:
            item = {
                'id': product.id,
                'external_id': product.external_id,
                'name': product.product.name,
                'category': product.product.category.name,
                'model': product.model,
                'shop': product.shop.name,
                'quantity': product.quantity,
                'price': product.price,
                'price_rrc': product.price_rrc,
                'parameters': {p.parameter.name: p.value for p in product.product_parameters.all()}
            }

            # Добавляем аналитику для магазинов
            if user.type == 'shop' and filters.get('detailed'):
                from django.db.models import Sum, F
                total_ordered = product.ordered_items.aggregate(total=Sum('quantity'))['total'] or 0
                revenue = product.ordered_items.aggregate(
                    total=Sum(F('quantity') * F('product_info__price'))
                )['total'] or 0
                item['total_ordered'] = total_ordered
                item['revenue'] = revenue

            data.append(item)

        # Создаем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'export_{user.email}_{timestamp}.{export_format}'
        filepath = os.path.join(settings.EXPORT_FILES_ROOT, filename)

        # Экспортируем в нужный формат
        if export_format == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        elif export_format == 'yaml':
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        elif export_format == 'csv':
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                if data:
                    # Получаем все возможные ключи из параметров
                    all_keys = set()
                    for item in data:
                        all_keys.update(item.keys())

                    writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                    writer.writeheader()
                    writer.writerows(data)

        # Отправляем email с ссылкой на файл
        send_export_email.delay(user_id, filename, len(data))

        # Очищаем старые файлы (старше 7 дней)
        cleanup_old_exports.delay()

        return {
            'status': 'success',
            'filename': filename,
            'filepath': filepath,
            'count': len(data),
            'format': export_format
        }

    except Exception as e:
        # В случае ошибки отправляем email об ошибке
        send_export_error_email.delay(user_id, str(e))
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def send_export_email(user_id, filename, count):
    """
    Отправка email уведомления о готовности экспорта
    """
    try:
        user = User.objects.get(id=user_id)

        # Создаем ссылку для скачивания
        download_url = f"http://localhost:8000/api/v1/products/export/download/{filename}"

        subject = f"Экспорт товаров готов - {filename}"
        message = f"""
        Уважаемый {user.first_name or user.email}!
        
        Ваш экспорт товаров успешно завершен.
        
        Статистика:
        - Экспортировано товаров: {count}
        - Формат файла: {filename.split('.')[-1].upper()}
        
        Скачать файл: {download_url}
        
        Файл будет доступен для скачивания в течение 7 дней.
        
        С уважением,
        Команда интернет-магазина
        """

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email]
        )
        email.send()

    except Exception as e:
        print(f"Ошибка отправки email: {e}")


@shared_task
def send_export_error_email(user_id, error_message):
    """
    Отправка email об ошибке экспорта
    """
    try:
        user = User.objects.get(id=user_id)

        subject = "Ошибка при экспорте товаров"
        message = f"""
        Уважаемый {user.first_name or user.email}!
        
        При выполнении экспорта товаров произошла ошибка:
        
        {error_message}
        
        Пожалуйста, попробуйте позже или обратитесь в поддержку.
        
        С уважением,
        Команда интернет-магазина
        """

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email]
        )
        email.send()

    except Exception as e:
        print(f"Ошибка отправки email: {e}")


@shared_task
def cleanup_old_exports():
    """
    Очистка старых файлов экспорта (старше 7 дней)
    """
    import os
    from datetime import timedelta
    from django.utils import timezone

    now = timezone.now()
    cutoff = now - timedelta(days=7)

    for filename in os.listdir(settings.EXPORT_FILES_ROOT):
        filepath = os.path.join(settings.EXPORT_FILES_ROOT, filename)
        file_modified = timezone.datetime.fromtimestamp(
            os.path.getmtime(filepath), tz=timezone.get_current_timezone()
        )

        if file_modified < cutoff:
            os.remove(filepath)
            print(f"Удален старый файл: {filename}")