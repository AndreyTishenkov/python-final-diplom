from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from celery import shared_task
import os


def process_image(image_field, sizes, quality=85):
    """
    Обработка изображения: создание миниатюр разных размеров

    sizes: список кортежей (ширина, высота, суффикс_поля)
    Пример: [(150, 150, 'thumbnail_small'), (300, 300, 'thumbnail_medium')]
    """
    if not image_field:
        return None

    results = {}

    try:
        # Открываем изображение
        img = Image.open(image_field.path)

        # Конвертируем в RGB если нужно (для PNG с прозрачностью)
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img

        # Создаём миниатюры для каждого размера
        for width, height, field_name in sizes:
            # Создаём копию для каждого размера
            img_copy = img.copy()

            # Изменяем размер с сохранением пропорций
            img_copy.thumbnail((width, height), Image.Resampling.LANCZOS)

            # Сохраняем в BytesIO
            output = BytesIO()
            img_copy.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)

            results[field_name] = ContentFile(output.read(), name=f"{field_name}_{os.path.basename(image_field.name)}")

        return results

    except Exception as e:
        print(f"Ошибка обработки изображения: {e}")
        return None


@shared_task
def process_user_avatar(user_id, image_path):
    """
    Асинхронная обработка аватара пользователя
    Создаёт миниатюры 100x100 и 200x200
    """
    from backend.models import User

    try:
        user = User.objects.get(id=user_id)

        if not user.avatar:
            return {'status': 'error', 'error': 'Нет аватара для обработки.'}

        sizes = [
            (100, 100, 'avatar_small'),
            (200, 200, 'avatar_medium'),
        ]

        results = process_image(user.avatar, sizes, quality=85)

        if results:
            for field_name, content in results.items():
                setattr(user, field_name, content)
            user.save()

        return {'status': 'success', 'user_id': user_id}

    except User.DoesNotExist:
        return {'status': 'error', 'error': 'Пользователь не найден.'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@shared_task
def process_product_main_image(product_id, image_path):
    """
    Асинхронная обработка главного изображения товара
    Создаёт миниатюры 150x150, 300x300, 600x600
    """
    from backend.models import Product

    try:
        product = Product.objects.get(id=product_id)

        if not product.main_image:
            return {'status': 'error', 'error': 'Нет картинки для обработки.'}

        sizes = [
            (150, 150, 'thumbnail_small'),
            (300, 300, 'thumbnail_medium'),
            (600, 600, 'thumbnail_large'),
        ]

        results = process_image(product.main_image, sizes, quality=85)

        if results:
            for field_name, content in results.items():
                setattr(product, field_name, content)
            product.save()

        return {'status': 'success', 'product_id': product_id}

    except Product.DoesNotExist:
        return {'status': 'error', 'error': 'Товар не найден.'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@shared_task
def process_product_gallery_images(product_image_id):
    """
    Асинхронная обработка изображений галереи товара
    """
    from backend.models import ProductImage

    try:
        product_image = ProductImage.objects.get(id=product_image_id)

        if not product_image.image:
            return {'status': 'error', 'error': 'Нет картинки для обработки.'}

        sizes = [
            (150, 150, 'thumbnail_small'),
            (300, 300, 'thumbnail_medium'),
        ]

        results = process_image(product_image.image, sizes, quality=80)

        if results:
            for field_name, content in results.items():
                setattr(product_image, field_name, content)
            product_image.save()

        return {'status': 'success', 'product_image_id': product_image_id}

    except ProductImage.DoesNotExist:
        return {'status': 'error', 'error': 'Картинка товара не найдена.'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}