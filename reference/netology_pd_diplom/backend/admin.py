from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db.models import Sum, F
from django.contrib import messages

from backend.models import (
    User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
    Order, OrderItem, Contact, ConfirmEmailToken
)
from backend.forms import UserAdminForm


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Панель управления пользователями с отображением аватара
    """
    model = User

    # Поля для отображения в списке
    list_display = ('email', 'first_name', 'last_name', 'type', 'avatar_preview', 'is_staff', 'is_active')

    # Фильтры
    list_filter = ('type', 'is_staff', 'is_active')

    # Поля для поиска
    search_fields = ('email', 'first_name', 'last_name')

    # Поля для отображения на странице редактирования
    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company', 'position')}),
        ('Avatar', {'fields': ('avatar', 'avatar_small', 'avatar_medium'), 'classes': ('collapse',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    # Поля для формы добавления нового пользователя
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'type', 'first_name', 'last_name', 'is_active', 'is_staff'),
        }),
    )

    def avatar_preview(self, obj):
        """Отображение миниатюры аватара в списке"""
        if obj.avatar:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius: 50%; object-fit: cover;" />',
                obj.avatar.url
            )
        return format_html(
            '<div style="width:40px; height:40px; background:#ccc; border-radius:50%; display:flex; align-items:center; justify-content:center;">📷</div>'
        )
    avatar_preview.short_description = 'Аватар'

    def save_model(self, request, obj, form, change):
        """Сохранение пользователя"""
        super().save_model(request, obj, form, change)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'state', 'url')
    list_filter = ('state',)
    search_fields = ('name', 'user__email')
    list_editable = ('state',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_shops')
    search_fields = ('name',)
    filter_horizontal = ('shops',)

    def get_shops(self, obj):
        return ", ".join([shop.name for shop in obj.shops.all()])
    get_shops.short_description = 'Магазины'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('product', 'shop', 'price', 'quantity', 'external_id')
    list_filter = ('shop', 'product__category')
    search_fields = ('product__name', 'shop__name', 'model')
    list_editable = ('price', 'quantity')


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ('product_info', 'parameter', 'value')
    list_filter = ('parameter',)
    search_fields = ('product_info__product__name', 'value')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """ Логика для работы с заказами в админке вынесены в папку admin_utils """
    pass


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_info', 'quantity')
    list_filter = ('order__state',)
    search_fields = ('order__id', 'product_info__product__name')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'street', 'house', 'phone')
    list_filter = ('city',)
    search_fields = ('user__email', 'city', 'street', 'phone')


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at',)
    search_fields = ('user__email', 'key')


class OrderItemInline(admin.TabularInline):
    """Товары в заказе для отображения внутри заказа"""
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