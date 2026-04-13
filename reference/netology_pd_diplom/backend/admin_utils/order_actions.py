from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from backend.models import Order


class OrderActionsMixin:
    """Миксин с действиями над заказами"""

    def confirm_order(self, request, order_id):
        """Подтверждение заказа"""
        order = get_object_or_404(Order, id=order_id)
        old_status = order.state
        if order.state == 'new':
            order.state = 'confirmed'
            order.save()
            self._send_status_notification(order, old_status, 'confirmed', request)
            self.message_user(request, f'Заказ #{order.id} подтвержден', messages.SUCCESS)
        else:
            self.message_user(request, f'Невозможно подтвердить заказ в статусе "{order.state}"', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:backend_order_changelist'))

    def cancel_order(self, request, order_id):
        """Отмена заказа"""
        order = get_object_or_404(Order, id=order_id)
        old_status = order.state
        if order.state not in ['delivered', 'canceled']:
            order.state = 'canceled'
            order.save()
            self._send_status_notification(order, old_status, 'canceled', request)
            self.message_user(request, f'Заказ #{order.id} отменен', messages.SUCCESS)
        else:
            self.message_user(request, f'Невозможно отменить заказ в статусе "{order.state}"', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:backend_order_changelist'))

    def assemble_order(self, request, order_id):
        """Сборка заказа"""
        order = get_object_or_404(Order, id=order_id)
        old_status = order.state
        if order.state == 'confirmed':
            order.state = 'assembled'
            order.save()
            self._send_status_notification(order, old_status, 'assembled', request)
            self.message_user(request, f'Заказ #{order.id} собран', messages.SUCCESS)
        else:
            self.message_user(request, f'Невозможно собрать заказ в статусе "{order.state}"', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:backend_order_changelist'))

    def send_order(self, request, order_id):
        """Отправка заказа"""
        order = get_object_or_404(Order, id=order_id)
        old_status = order.state
        if order.state == 'assembled':
            order.state = 'sent'
            order.save()
            self._send_status_notification(order, old_status, 'sent', request)
            self.message_user(request, f'Заказ #{order.id} отправлен', messages.SUCCESS)
        else:
            self.message_user(request, f'Невозможно отправить заказ в статусе "{order.state}"', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:backend_order_changelist'))

    def deliver_order(self, request, order_id):
        """Доставка заказа"""
        order = get_object_or_404(Order, id=order_id)
        old_status = order.state
        if order.state == 'sent':
            order.state = 'delivered'
            order.save()
            self._send_status_notification(order, old_status, 'delivered', request)
            self.message_user(request, f'Заказ #{order.id} доставлен', messages.SUCCESS)
        else:
            self.message_user(request, f'Невозможно доставить заказ в статусе "{order.state}"', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:backend_order_changelist'))

    def send_notification(self, request, order_id):
        """Отправка уведомления о статусе заказа"""
        order = get_object_or_404(Order, id=order_id)
        self._send_status_notification(order, order.state, order.state, request, force=True)
        return HttpResponseRedirect(reverse('admin:backend_order_changelist'))

    def confirm_orders(self, request, queryset):
        """Массовое подтверждение заказов"""
        updated = 0
        for order in queryset:
            if order.state == 'new':
                old_status = order.state
                order.state = 'confirmed'
                order.save()
                self._send_status_notification(order, old_status, 'confirmed', request)
                updated += 1
        self.message_user(request, f'Подтверждено заказов: {updated}', messages.SUCCESS)
    confirm_orders.short_description = 'Подтвердить выбранные заказы'

    def cancel_orders(self, request, queryset):
        """Массовая отмена заказов"""
        updated = 0
        for order in queryset:
            if order.state not in ['delivered', 'canceled']:
                old_status = order.state
                order.state = 'canceled'
                order.save()
                self._send_status_notification(order, old_status, 'canceled', request)
                updated += 1
        self.message_user(request, f'Отменено заказов: {updated}', messages.SUCCESS)
    cancel_orders.short_description = 'Отменить выбранные заказы'