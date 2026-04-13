from django.contrib.admin import AdminSite
from django.urls import path
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from backend.models import Order, User, ProductInfo, Shop


class CustomAdminSite(AdminSite):
    site_header = 'Магазин Электроники "Тишенков-Shop"'
    site_title = 'Админ панель'
    index_title = 'Дашборд управления магазином'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard), name='dashboard'),
        ]
        return custom_urls + urls

    def dashboard(self, request):
        from django.shortcuts import render

        # Статистика за сегодня
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        context = {
            'title': 'Дашборд',
            # Заказы
            'total_orders': Order.objects.exclude(state='basket').count(),
            'new_orders': Order.objects.filter(state='new').count(),
            'confirmed_orders': Order.objects.filter(state='confirmed').count(),
            'delivered_orders': Order.objects.filter(state='delivered').count(),
            'canceled_orders': Order.objects.filter(state='canceled').count(),
            'today_orders': Order.objects.filter(dt__date=today).count(),
            # Пользователи
            'total_users': User.objects.count(),
            'new_users': User.objects.filter(date_joined__date=today).count(),
            'active_shops': Shop.objects.filter(state=True).count(),
            # Товары
            'total_products': ProductInfo.objects.count(),
            'low_stock': ProductInfo.objects.filter(quantity__lt=10).count(),
            # Выручка
            'revenue_today': self._get_today_revenue(),
            'revenue_month': self._get_month_revenue(),
        }
        return render(request, 'admin/dashboard.html', context)

    def _get_today_revenue(self):
        today = timezone.now().date()
        orders = Order.objects.filter(
            state='delivered',
            dt__date=today
        )
        total = 0
        for order in orders:
            for item in order.ordered_items.all():
                total += item.quantity * item.product_info.price
        return total

    def _get_month_revenue(self):
        month_ago = timezone.now() - timedelta(days=30)
        orders = Order.objects.filter(
            state='delivered',
            dt__gte=month_ago
        )
        total = 0
        for order in orders:
            for item in order.ordered_items.all():
                total += item.quantity * item.product_info.price
        return total


# Заменяем стандартный AdminSite
admin_site = CustomAdminSite(name='myadmin')