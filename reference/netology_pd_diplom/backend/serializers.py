# Верстальщик
from rest_framework import serializers

from backend.models import User, Category, Shop, ProductInfo, Product, ProductParameter, OrderItem, Order, Contact


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure', 'building', 'apartment', 'user', 'phone')
        read_only_fields = ('id',)
        extra_kwargs = {
            'user': {'write_only': True}
        }


class UserSerializer(serializers.ModelSerializer):

    """
    Сериализатор для модели пользователя.

    Используется для:
    - Регистрации нового пользователя
    - Просмотра и редактирования профиля
    """

    contacts = ContactSerializer(read_only=True, many=True)

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'company', 'position', 'contacts')
        read_only_fields = ('id',)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name',)
        read_only_fields = ('id',)


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'state',)
        read_only_fields = ('id',)


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = ('name', 'category',)


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value',)


class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)

    class Meta:
        model = ProductInfo
        fields = ('id', 'model', 'product', 'shop', 'quantity', 'price', 'price_rrc', 'product_parameters',)
        read_only_fields = ('id',)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity', 'order',)
        read_only_fields = ('id',)
        extra_kwargs = {
            'order': {'write_only': True}
        }


class OrderItemCreateSerializer(OrderItemSerializer):
    product_info = ProductInfoSerializer(read_only=True)


class OrderSerializer(serializers.ModelSerializer):

    """
    Сериализатор для модели заказа.

    Включает:
    - Список товаров в заказе
    - Общую сумму
    - Информацию о контакте
    """

    ordered_items = OrderItemCreateSerializer(read_only=True, many=True)

    total_sum = serializers.IntegerField()
    contact = ContactSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'ordered_items', 'state', 'dt', 'total_sum', 'contact',)
        read_only_fields = ('id',)


class ProductExportSerializer(serializers.ModelSerializer):
    """
    Сериализатор для экспорта товаров с полной информацией
    """
    category = serializers.StringRelatedField()
    shop_name = serializers.CharField(source='shop.name')
    shop_state = serializers.BooleanField(source='shop.state')
    product_name = serializers.CharField(source='product.name')
    parameters = serializers.SerializerMethodField()

    class Meta:
        model = ProductInfo
        fields = (
            'id', 'external_id', 'product_name', 'category',
            'model', 'shop_name', 'shop_state', 'quantity',
            'price', 'price_rrc', 'parameters', 'created_at'
        )

    def get_parameters(self, obj):
        """Собирает параметры товара в словарь"""
        params = {}
        for param in obj.product_parameters.all():
            params[param.parameter.name] = param.value
        return params


class ProductExportFullSerializer(serializers.ModelSerializer):
    """
    Расширенный сериализатор для экспорта с деталями заказов
    """
    product = ProductSerializer(read_only=True)
    shop = ShopSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)
    total_ordered = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()

    class Meta:
        model = ProductInfo
        fields = (
            'id', 'external_id', 'product', 'model', 'shop',
            'quantity', 'price', 'price_rrc', 'product_parameters',
            'total_ordered', 'revenue'
        )

    def get_total_ordered(self, obj):
        """Считает сколько единиц товара заказано"""
        from django.db.models import Sum
        total = obj.ordered_items.aggregate(total=Sum('quantity'))['total']
        return total or 0

    def get_revenue(self, obj):
        """Считает выручку по товару"""
        from django.db.models import Sum, F
        revenue = obj.ordered_items.aggregate(
            total=Sum(F('quantity') * F('product_info__price'))
        )['total']
        return revenue or 0