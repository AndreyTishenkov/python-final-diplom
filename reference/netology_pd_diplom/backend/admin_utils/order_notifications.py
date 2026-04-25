from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib import messages
from backend.tasks import send_order_status_email


class OrderNotificationsMixin:
    """Миксин для отправки уведомлений о заказах"""

    STATUS_NAMES = {
        'new': 'Новый',
        'confirmed': 'Подтвержден',
        'assembled': 'Собран',
        'sent': 'Отправлен',
        'delivered': 'Доставлен',
        'canceled': 'Отменен',
    }

    def _send_status_notification(self, order, old_status, new_status, request, force=False):
        """
        Отправка email уведомления об изменении статуса
        АСИНХРОННО через Celery
        """
        # Вместо синхронной отправки - ставим задачу в очередь Celery
        send_order_status_email.delay(order.id, old_status, new_status)

        if not force:
            self.message_user(
                request,
                f'Задача на отправку уведомления для заказа #{order.id} поставлена в очередь',
                messages.SUCCESS
            )