from typing import Type

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User
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