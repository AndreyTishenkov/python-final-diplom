from typing import Type

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User, Product, Category, Shop, ProductInfo
from backend.tasks import send_registration_email, send_password_reset_email, send_order_status_email

new_user_registered = Signal()
new_order = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправка письма с токеном для сброса пароля (асинхронно через Celery)
    """
    send_password_reset_email.delay(reset_password_token.user.id, reset_password_token.key)


@receiver(post_save, sender=User)
def new_user_registered_signal(sender, instance, created, **kwargs):
    """
    Отправка письма с подтверждением почты (асинхронно через Celery)
    """
    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)
        send_registration_email.delay(instance.pk, token.key)


@receiver(new_order)
def new_order_signal(sender, user_id, order_id, **kwargs):
    """
    Отправка письма при создании нового заказа (асинхронно через Celery)
    """
    send_order_status_email.delay(order_id, 'basket', 'new')


# ========== КЭШИРОВАНИЕ ТОВАРОВ ==========

def invalidate_all_product_caches():
    """Полная очистка всех кэшей, связанных с товарами"""
    cache.delete_pattern('*products*')
    cache.delete_pattern('*product*')
    cache.delete_pattern('*ProductInfo*')
    cache.delete_pattern('*.views.decorators.cache.cache_page.*')
    print("[CACHE] Все кэши товаров очищены")


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    """Очищаем кэш при изменении товара"""
    cache.delete(f'product_{instance.id}')
    invalidate_all_product_caches()


@receiver(post_save, sender=ProductInfo)
@receiver(post_delete, sender=ProductInfo)
def invalidate_product_info_cache(sender, instance, **kwargs):
    """Очищаем кэш при изменении информации о товаре (цена, количество)"""
    # Очищаем кэш конкретного товара
    cache.delete(f'product_info_{instance.id}')
    cache.delete(f'product_{instance.product.id}')
    # Очищаем все списки товаров
    invalidate_all_product_caches()
    print(f"[CACHE] Инвалидирован кэш ProductInfo ID={instance.id}")


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_category_cache(sender, instance, **kwargs):
    """Очищаем кэш категорий"""
    cache.delete_pattern('*categories*')
    cache.delete_pattern('*category*')
    # Также очищаем товары, так как они связаны с категориями
    invalidate_all_product_caches()
    print(f"[CACHE] Инвалидирован кэш категории ID={instance.id}")


@receiver(post_save, sender=Shop)
@receiver(post_delete, sender=Shop)
def invalidate_shop_cache(sender, instance, **kwargs):
    """Очищаем кэш магазинов"""
    cache.delete_pattern('*shops*')
    cache.delete_pattern('*shop*')
    # Также очищаем товары, так как они связаны с магазинами
    invalidate_all_product_caches()
    print(f"[CACHE] Инвалидирован кэш магазина ID={instance.id}")