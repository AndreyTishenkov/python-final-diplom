from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.db.models import Sum, F

from backend.models import Order, OrderItem
from backend.admin_utils.order_actions import OrderActionsMixin
from backend.admin_utils.order_notifications import OrderNotificationsMixin


class OrderItemInline(admin.TabularInline):
    """Товары в заказе"""
    model = OrderItem
    extra = 0
    readonly_fields = ('product_info', 'quantity', 'get_product_name', 'get_price', 'get_total')
    fields = ('get_product_name', 'quantity', 'get_price', 'get_total')
    can_delete = False
    max_num = 0

    def get_product_name(self, obj):
        return obj.product_info.product.name
    get_product_name.short_description = 'Товар'

    def get_price(self, obj):
        return f"{obj.product_info.price} ₽"
    get_price.short_description = 'Цена'

    def get_total(self, obj):
        total = obj.quantity * obj.product_info.price
        return f"{total} ₽"
    get_total.short_description = 'Сумма'


class CustomOrderAdmin(OrderActionsMixin, OrderNotificationsMixin, admin.ModelAdmin):
    """Расширенная админка для управления заказами"""

    list_display = ('id', 'user_info', 'status_badge', 'total_sum_display', 'dt', 'contact_short', 'action_buttons')
    list_filter = ('state', 'dt')
    search_fields = ('id', 'user__email', 'user__first_name', 'user__last_name', 'contact__phone')
    readonly_fields = ('dt', 'total_sum_display', 'items_list', 'user_detailed', 'contact_detailed')
    inlines = [OrderItemInline]
    list_per_page = 20
    list_select_related = ('user', 'contact')

    fieldsets = (
        ('Информация о заказе', {
            'fields': ('id', 'state', 'dt', 'total_sum_display')
        }),
        ('Покупатель', {
            'fields': ('user_detailed',)
        }),
        ('Контактные данные', {
            'fields': ('contact_detailed',)
        }),
        ('Товары в заказе', {
            'fields': ('items_list',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).select_related('user', 'contact').prefetch_related(
            'ordered_items__product_info__product',
            'ordered_items__product_info__shop'
        )

    def user_info(self, obj):
        if obj.user:
            return format_html(
                '<strong>{}</strong><br/>{}',
                obj.user.get_full_name() or obj.user.email,
                obj.user.email
            )
        return '-'
    user_info.short_description = 'Покупатель'

    def user_detailed(self, obj):
        if obj.user:
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Имя:</strong> {}<br/>'
                '<strong>Email:</strong> {}<br/>'
                '<strong>Тип:</strong> {}<br/>'
                '<strong>Компания:</strong> {}<br/>'
                '<strong>Должность:</strong> {}<br/>'
                '</div>',
                obj.user.get_full_name() or 'Не указано',
                obj.user.email,
                'Магазин' if obj.user.type == 'shop' else 'Покупатель',
                obj.user.company or 'Не указана',
                obj.user.position or 'Не указана'
            )
        return '-'
    user_detailed.short_description = 'Детали покупателя'

    def contact_short(self, obj):
        if obj.contact:
            return format_html(
                '{}<br/>{}',
                obj.contact.city,
                obj.contact.phone
            )
        return '-'
    contact_short.short_description = 'Контакты'

    def contact_detailed(self, obj):
        if obj.contact:
            return format_html(
                '<div style="background: #e9ecef; padding: 10px; border-radius: 5px;">'
                '<strong>Город:</strong> {}<br/>'
                '<strong>Адрес:</strong> ул. {}, д. {}{}<br/>'
                '<strong>Телефон:</strong> {}<br/>'
                '</div>',
                obj.contact.city,
                obj.contact.street,
                obj.contact.house,
                f', кв. {obj.contact.apartment}' if obj.contact.apartment else '',
                obj.contact.phone
            )
        return '-'
    contact_detailed.short_description = 'Детали доставки'

    def total_sum_display(self, obj):
        total = obj.total_sum if hasattr(obj, 'total_sum') and obj.total_sum else 0
        return format_html(
            '<span style="font-size: 14px; font-weight: bold;">{} ₽</span>',
            f"{total:,.0f}".replace(",", " ")
        )
    total_sum_display.short_description = 'Сумма заказа'

    def items_list(self, obj):
        items = obj.ordered_items.select_related('product_info__product', 'product_info__shop')
        if not items:
            return '-'

        html = '<div style="max-height: 300px; overflow-y: auto;">'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        html += '<thead><tr style="background: #f2f2f2;">'
        html += '<th style="padding: 8px; text-align: left;">Товар</th>'
        html += '<th style="padding: 8px; text-align: left;">Магазин</th>'
        html += '<th style="padding: 8px; text-align: center;">Кол-во</th>'
        html += '<th style="padding: 8px; text-align: right;">Цена</th>'
        html += '<th style="padding: 8px; text-align: right;">Сумма</th>'
        html += '</tr></thead><tbody>'

        for item in items:
            total = item.quantity * item.product_info.price
            html += f'''
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;"><strong>{item.product_info.product.name}</strong><br/><small>{item.product_info.model}</small></td>
                <td style="padding: 8px;">{item.product_info.shop.name}</td>
                <td style="padding: 8px; text-align: center;">{item.quantity}</td>
                <td style="padding: 8px; text-align: right;">{item.product_info.price:,.0f} ₽</td>
                <td style="padding: 8px; text-align: right;"><strong>{total:,.0f} ₽</strong></td>
            </tr>
            '''

        html += '</tbody></table></div>'
        return format_html(html)
    items_list.short_description = 'Состав заказа'

    def status_badge(self, obj):
        status_colors = {
            'basket': '#6c757d',
            'new': '#007bff',
            'confirmed': '#28a745',
            'assembled': '#fd7e14',
            'sent': '#6f42c1',
            'delivered': '#20c997',
            'canceled': '#dc3545',
        }
        status_names = {
            'basket': 'Корзина',
            'new': 'Новый',
            'confirmed': 'Подтвержден',
            'assembled': 'Собран',
            'sent': 'Отправлен',
            'delivered': 'Доставлен',
            'canceled': 'Отменен',
        }
        color = status_colors.get(obj.state, '#000')
        name = status_names.get(obj.state, obj.state)
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">{}</span>',
            color, name
        )
    status_badge.short_description = 'Статус'

    def action_buttons(self, obj):
        buttons = []

        if obj.state != 'basket' and obj.state != 'canceled' and obj.state != 'delivered':
            if obj.state == 'new':
                buttons.append(f'<a class="button" href="../confirm/{obj.id}/" style="background: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin-right: 4px;">Подтвердить</a>')
                buttons.append(f'<a class="button" href="../cancel/{obj.id}/" style="background: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px;">Отменить</a>')
            elif obj.state == 'confirmed':
                buttons.append(f'<a class="button" href="../assemble/{obj.id}/" style="background: #fd7e14; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin-right: 4px;">Собрать</a>')
                buttons.append(f'<a class="button" href="../cancel/{obj.id}/" style="background: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px;">Отменить</a>')
            elif obj.state == 'assembled':
                buttons.append(f'<a class="button" href="../send/{obj.id}/" style="background: #17a2b8; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px;">Отправить</a>')
            elif obj.state == 'sent':
                buttons.append(f'<a class="button" href="../deliver/{obj.id}/" style="background: #20c997; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px;">Доставить</a>')

        if obj.state != 'basket':
            buttons.append(f'<br/><a class="button" href="../send-email/{obj.id}/" style="background: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin-top: 5px; display: inline-block;">Отправить уведомление</a>')

        return format_html(''.join(buttons)) if buttons else '-'
    action_buttons.short_description = 'Действия'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('confirm/<int:order_id>/', self.confirm_order, name='confirm-order'),
            path('cancel/<int:order_id>/', self.cancel_order, name='cancel-order'),
            path('assemble/<int:order_id>/', self.assemble_order, name='assemble-order'),
            path('send/<int:order_id>/', self.send_order, name='send-order'),
            path('deliver/<int:order_id>/', self.deliver_order, name='deliver-order'),
            path('send-email/<int:order_id>/', self.send_notification, name='send-notification'),
        ]
        return custom_urls + urls

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions['confirm_orders'] = (self.confirm_orders, 'confirm_orders', 'Подтвердить выбранные заказы')
        actions['cancel_orders'] = (self.cancel_orders, 'cancel_orders', 'Отменить выбранные заказы')
        return actions