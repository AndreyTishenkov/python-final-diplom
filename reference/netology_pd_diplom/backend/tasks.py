import os
import json
import csv
import yaml
from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from celery import shared_task
from backend.models import (
    ProductInfo, User, Shop, Category, Product,
    Parameter, ProductParameter, Order, ConfirmEmailToken
)
from io import StringIO
from requests import get
from yaml import load as load_yaml, Loader


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
        return {'status': 'error', 'error': str(e)}


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
        Интернет-магазин "Тишенков-Shop"
        """

        email = EmailMultiAlternatives(
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
        Интернет-магазин "Тишенков-Shop"
        """

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email]
        )
        email.send()

    except Exception as e:
        print(f"Ошибка отправки email: {e}")


# ========== ИМПОРТ ТОВАРОВ ИЗ YAML ==========
@shared_task
def async_import_products(user_id, yaml_content, shop_name=None):
    """
    Асинхронный импорт товаров из YAML
    """
    try:
        user = User.objects.get(id=user_id)

        # Парсим YAML
        data = load_yaml(StringIO(yaml_content), Loader=Loader)

        # Получаем или создаем магазин
        shop_name = shop_name or data.get('shop', f"Магазин {user.email}")
        shop, _ = Shop.objects.get_or_create(
            name=shop_name,
            defaults={'user': user, 'state': True}
        )

        imported_count = 0
        categories_cache = {}

        # Импортируем категории
        for category_data in data.get('categories', []):
            cat_id = category_data['id']
            cat_name = category_data['name']

            category, _ = Category.objects.get_or_create(
                id=cat_id,
                defaults={'name': cat_name}
            )
            category.shops.add(shop)
            categories_cache[cat_id] = category

        # Импортируем товары
        for item in data.get('goods', []):
            category = categories_cache.get(item['category'])
            if not category:
                continue

            product, _ = Product.objects.get_or_create(
                name=item['name'],
                category=category
            )

            product_info, created = ProductInfo.objects.update_or_create(
                external_id=item['id'],
                shop=shop,
                defaults={
                    'product': product,
                    'model': item.get('model', ''),
                    'price': item['price'],
                    'price_rrc': item.get('price_rrc', item['price']),
                    'quantity': item.get('quantity', 0)
                }
            )

            # Импортируем параметры
            for param_name, param_value in item.get('parameters', {}).items():
                parameter, _ = Parameter.objects.get_or_create(name=param_name)
                ProductParameter.objects.update_or_create(
                    product_info=product_info,
                    parameter=parameter,
                    defaults={'value': str(param_value)}
                )

            imported_count += 1

        # Отправляем уведомление об успехе
        send_import_success_email.delay(user_id, imported_count, shop.name)

        return {
            'status': 'success',
            'imported_count': imported_count,
            'shop_name': shop.name
        }

    except Exception as e:
        send_import_error_email.delay(user_id, str(e))
        return {'status': 'error', 'error': str(e)}


@shared_task
def send_import_success_email(user_id, count, shop_name):
    """Уведомление об успешном импорте"""
    try:
        user = User.objects.get(id=user_id)

        subject = "Импорт товаров завершен"
        message = f"""
            Здравствуйте, {user.first_name or user.email}!

            Импорт товаров в магазин "{shop_name}" успешно завершен.

            Статистика:
                - Импортировано товаров: {count}

            С уважением,
            Интернет-магазин "Тишенков-Shop"
            """

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email]
        )
        email.send()

    except Exception as e:
        print(f"Ошибка отправки email: {e}")


@shared_task
def send_import_error_email(user_id, error_message):
    """Уведомление об ошибке импорта"""
    try:
        user = User.objects.get(id=user_id)

        subject = "Ошибка при импорте товаров"
        message = f"""
            Здравствуйте, {user.first_name or user.email}!

            При импорте товаров произошла ошибка:

            {error_message}

            Пожалуйста, проверьте файл и попробуйте снова.

            С уважением,
            Интернет-магазин "Тишенков-Shop"
            """

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email]
        )
        email.send()

    except Exception as e:
        print(f"Ошибка отправки email: {e}")


# ========== ОБНОВЛЕНИЕ ПРАЙС-ЛИСТА ==========
@shared_task
def async_update_price_list(user_id, url):
    """
    Асинхронное обновление прайс-листа магазина
    """
    try:
        user = User.objects.get(id=user_id)

        if user.type != 'shop':
            return {'status': 'error', 'error': 'Только для магазинов'}

        # Валидация URL
        validate_url = URLValidator()
        try:
            validate_url(url)
        except ValidationError as e:
            return {'status': 'error', 'error': str(e)}

        # Скачиваем файл
        response = get(url)
        data = load_yaml(response.content, Loader=Loader)

        # Обновляем магазин
        shop, _ = Shop.objects.get_or_create(
            name=data['shop'],
            user_id=user.id
        )

        # Обновляем категории
        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(
                id=category['id'],
                name=category['name']
            )
            category_object.shops.add(shop.id)

        # Удаляем старые товары
        ProductInfo.objects.filter(shop_id=shop.id).delete()

        # Добавляем новые товары
        imported_count = 0
        for item in data['goods']:
            product, _ = Product.objects.get_or_create(
                name=item['name'],
                category_id=item['category']
            )

            product_info = ProductInfo.objects.create(
                product_id=product.id,
                external_id=item['id'],
                model=item.get('model', ''),
                price=item['price'],
                price_rrc=item.get('price_rrc', item['price']),
                quantity=item.get('quantity', 0),
                shop_id=shop.id
            )

            for name, value in item.get('parameters', {}).items():
                parameter_object, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(
                    product_info_id=product_info.id,
                    parameter_id=parameter_object.id,
                    value=str(value)
                )

            imported_count += 1

        # Уведомление об успехе
        send_update_success_email.delay(user_id, imported_count, shop.name)

        return {
            'status': 'success',
            'imported_count': imported_count,
            'shop_name': shop.name
        }

    except Exception as e:
        send_update_error_email.delay(user_id, str(e))
        return {'status': 'error', 'error': str(e)}


@shared_task
def send_update_success_email(user_id, count, shop_name):
    """Уведомление об успешном обновлении прайс-листа"""
    try:
        user = User.objects.get(id=user_id)

        subject = "Обновление прайс-листа завершено"
        message = f"""
            Здравствуйте, {user.first_name or user.email}!

            Прайс-лист магазина "{shop_name}" успешно обновлен.

            Статистика:
                - Обновлено товаров: {count}

            С уважением,
            Интернет-магазин "Тишенков-Shop"
            """

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email]
        )
        email.send()

    except Exception as e:
        print(f"Ошибка отправки email: {e}")


@shared_task
def send_update_error_email(user_id, error_message):
    """Уведомление об ошибке обновления"""
    try:
        user = User.objects.get(id=user_id)

        subject = "Ошибка при обновлении прайс-листа"
        message = f"""
            Здравствуйте, {user.first_name or user.email}!

            При обновлении прайс-листа произошла ошибка:

            {error_message}

            Пожалуйста, проверьте URL файла и попробуйте снова.

            С уважением,
            Интернет-магазин "Тишенков-Shop"
            """

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email]
        )
        email.send()

    except Exception as e:
        print(f"Ошибка отправки email: {e}")


# email-уведомления
@shared_task
def async_send_email(subject, message, to_email, from_email=None):
    """
    Асинхронная отправка email
    """
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=from_email or settings.EMAIL_HOST_USER,
            to=[to_email]
        )
        email.send()
        return {'status': 'success', 'to': to_email}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@shared_task
def async_send_order_status_email(order_id, old_status, new_status):
    """
    Асинхронная отправка уведомления об изменении статуса заказа
    """
    try:
        from backend.admin_utils.order_notifications import OrderNotificationsMixin
        # Используем существующий миксин для формирования письма
        # Этот код будет вызван из админки
        pass
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")


# ========== ОЧИСТКА СТАРЫХ ФАЙЛОВ ==========
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