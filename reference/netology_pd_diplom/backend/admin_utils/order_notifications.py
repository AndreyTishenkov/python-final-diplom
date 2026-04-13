from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib import messages


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
        """Отправка email уведомления об изменении статуса"""

        items_text = ""
        for item in order.ordered_items.select_related('product_info__product'):
            total = item.quantity * item.product_info.price
            items_text += f"- {item.product_info.product.name} x{item.quantity} = {total:,.0f} ₽\n"

        subject = f"Статус вашего заказа #{order.id} изменен"

        text_message = f"""
Здравствуйте, {order.user.first_name or order.user.email}!

Статус вашего заказа #{order.id} был изменен.

Предыдущий статус: {self.STATUS_NAMES.get(old_status, old_status)}
Новый статус: {self.STATUS_NAMES.get(new_status, new_status)}

Состав заказа:
{items_text}
ИТОГО: {order.total_sum if hasattr(order, 'total_sum') else 0:,.0f} ₽

С уважением,
Интернет-магазин
"""

        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=settings.EMAIL_HOST_USER,
                to=[order.user.email]
            )
            email.send()
            if not force:
                self.message_user(request, f'Уведомление отправлено пользователю {order.user.email}', messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f'Ошибка отправки уведомления: {e}', messages.ERROR)