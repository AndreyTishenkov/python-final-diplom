from distutils.util import strtobool
from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse, FileResponse
from requests import get
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from ujson import loads as load_json
from yaml import load as load_yaml, Loader
import json  # Добавлен импорт json
import csv   # Добавлен импорт csv
import os
from datetime import datetime  # Добавлен для работы с датами
from django.utils import timezone
from django.shortcuts import render

from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken, User

from backend.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, ContactSerializer, ProductExportSerializer, ProductExportFullSerializer

from backend.signals import new_user_registered, new_order


def index(request):
    """ Главная страница магазина """
    return render(request, 'index.html')

def admin_dashboard(request):
    """Дашборд для админки"""
    return render(request, 'admin/dashboard.html')


class RegisterAccount(APIView):
    """
    Для регистрации покупателей
    """

    # Регистрация методом POST

    def post(self, request, *args, **kwargs):
        """
            Process a POST request and create a new user.

            Args:
                request (Request): The Django request object.

            Returns:
                JsonResponse: The response indicating the status of the operation and any errors.
            """
        # проверяем обязательные аргументы
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):

            # проверяем пароль на сложность
            sad = 'asd'
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                # проверяем данные для уникальности имени пользователя

                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        """
                Подтверждает почтовый адрес пользователя.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        # проверяем обязательные аргументы
        if {'email', 'token'}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class AccountDetails(APIView):
    """
    A class for managing user account details.

    Methods:
    - get: Retrieve the details of the authenticated user.
    - post: Update the account details of the authenticated user.

    Attributes:
    - None
    """

    # получить данные
    def get(self, request: Request, *args, **kwargs):
        """
               Retrieve the details of the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the details of the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Редактирование методом POST
    def post(self, request, *args, **kwargs):
        """
                Update the account details of the authenticated user.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        # проверяем обязательные аргументы

        if 'password' in request.data:
            errors = {}
            # проверяем пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                request.user.set_password(request.data['password'])

        # проверяем остальные данные
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """

    # Авторизация методом POST
    def post(self, request, *args, **kwargs):
        """
                Authenticate a user.

                Args:
                    request (Request): The Django request object.

                Returns:
                    JsonResponse: The response indicating the status of the operation and any errors.
                """
        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'], password=request.data['password'])

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)

                    return JsonResponse({'Status': True, 'Token': token.key})

            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
        A class for searching products.

        Methods:
        - get: Retrieve the product information based on the specified filters.

        Attributes:
        - None
        """

    def get(self, request: Request, *args, **kwargs):
        """
               Retrieve the product information based on the specified filters.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the product information.
               """
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # фильтруем и отбрасываем дуликаты
        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data)


class BasketView(APIView):
    """
    A class for managing the user's shopping basket.

    Methods:
    - get: Retrieve the items in the user's basket.
    - post: Add an item to the user's basket.
    - put: Update the quantity of an item in the user's basket.
    - delete: Remove an item from the user's basket.

    Attributes:
    - None
    """

    # получить корзину
    def get(self, request, *args, **kwargs):
        """
                Retrieve the items in the user's basket.

                Args:
                - request (Request): The Django request object.

                Returns:
                - Response: The response containing the items in the user's basket.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # редактировать корзину
    def post(self, request, *args, **kwargs):
        """
               Add an items to the user's basket.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_created = 0
                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors': str(error)})
                        else:
                            objects_created += 1

                    else:

                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

                return JsonResponse({'Status': True, 'Создано объектов': objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить товары из корзины
    def delete(self, request, *args, **kwargs):
        """
                Remove  items from the user's basket.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # добавить позиции в корзину
    def put(self, request, *args, **kwargs):
        """
               Update the items in the user's basket.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0
                for order_item in items_dict:
                    if type(order_item['id']) == int and type(order_item['quantity']) == int:
                        objects_updated += OrderItem.objects.filter(order_id=basket.id, id=order_item['id']).update(
                            quantity=order_item['quantity'])

                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerUpdate(APIView):
    """
    A class for updating partner information.

    Methods:
    - post: Update the partner information.

    Attributes:
    - None
    """

    def post(self, request, *args, **kwargs):
        """
                Update the partner price list information.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})
            else:
                stream = get(url).content

                data = load_yaml(stream, Loader=Loader)

                shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
                for category in data['categories']:
                    category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
                    category_object.shops.add(shop.id)
                    category_object.save()
                ProductInfo.objects.filter(shop_id=shop.id).delete()
                for item in data['goods']:
                    product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

                    product_info = ProductInfo.objects.create(product_id=product.id,
                                                              external_id=item['id'],
                                                              model=item['model'],
                                                              price=item['price'],
                                                              price_rrc=item['price_rrc'],
                                                              quantity=item['quantity'],
                                                              shop_id=shop.id)
                    for name, value in item['parameters'].items():
                        parameter_object, _ = Parameter.objects.get_or_create(name=name)
                        ProductParameter.objects.create(product_info_id=product_info.id,
                                                        parameter_id=parameter_object.id,
                                                        value=value)

                return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerState(APIView):
    """
       A class for managing partner state.

       Methods:
       - get: Retrieve the state of the partner.

       Attributes:
       - None
       """
    # получить текущий статус
    def get(self, request, *args, **kwargs):
        """
               Retrieve the state of the partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the state of the partner.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # изменить текущий статус
    def post(self, request, *args, **kwargs):
        """
               Update the state of a partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)
        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=strtobool(state))
                return JsonResponse({'Status': True})
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerOrders(APIView):
    """
    Класс для получения заказов поставщиками
     Methods:
    - get: Retrieve the orders associated with the authenticated partner.

    Attributes:
    - None
    """

    def get(self, request, *args, **kwargs):
        """
               Retrieve the orders associated with the authenticated partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the orders associated with the partner.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """
       A class for managing contact information.

       Methods:
       - get: Retrieve the contact information of the authenticated user.
       - post: Create a new contact for the authenticated user.
       - put: Update the contact information of the authenticated user.
       - delete: Delete the contact of the authenticated user.

       Attributes:
       - None
       """

    # получить мои контакты
    def get(self, request, *args, **kwargs):
        """
               Retrieve the contact information of the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the contact information.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    # добавить новый контакт
    def post(self, request, *args, **kwargs):
        """
               Create a new contact for the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'city', 'street', 'phone'}.issubset(request.data):
            request.data._mutable = True
            request.data.update({'user': request.user.id})
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить контакт
    def delete(self, request, *args, **kwargs):
        """
               Delete the contact of the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # редактировать контакт
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            """
                   Update the contact information of the authenticated user.

                   Args:
                   - request (Request): The Django request object.

                   Returns:
                   - JsonResponse: The response indicating the status of the operation and any errors.
                   """
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                print(contact)
                if contact:
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True})
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class OrderView(APIView):
    """
    Класс для получения и размешения заказов пользователями
    Methods:
    - get: Retrieve the details of a specific order.
    - post: Create a new order.
    - put: Update the details of a specific order.
    - delete: Delete a specific order.

    Attributes:
    - None
    """

    # получить мои заказы
    def get(self, request, *args, **kwargs):
        """
               Retrieve the details of user orders.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the details of the order.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    # разместить заказ из корзины
    def post(self, request, *args, **kwargs):
        """
               Put an order and send a notification.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit():
                try:
                    is_updated = Order.objects.filter(
                        user_id=request.user.id, id=request.data['id']).update(
                        contact_id=request.data['contact'],
                        state='new')
                except IntegrityError as error:
                    print(error)
                    return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'})
                else:
                    if is_updated:
                        new_order.send(sender=self.__class__, user_id=request.user.id)
                        return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


# Импорт задач Celery
try:
    from backend.tasks import async_export_products
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    async_export_products = None


class ProductExportView(APIView):
    """
    Класс для экспорта товаров в различных форматах

    Поддерживаемые форматы:
    - json (по умолчанию)
    - yaml
    - csv

    Параметры фильтрации:
    - shop_id: ID магазина
    - category_id: ID категории
    - min_price: минимальная цена
    - max_price: максимальная цена
    - in_stock: только товары в наличии (true/false)
    - format: формат выдачи (json/yaml/csv)
    """

    def get(self, request, *args, **kwargs):
        """
        Экспорт товаров с фильтрацией
        """
        # Проверяем права доступа (только для авторизованных магазинов)
        if request.user.is_authenticated and request.user.type == 'shop':
            # Магазин видит только свои товары
            queryset = ProductInfo.objects.filter(shop__user_id=request.user.id)
        else:
            # Публичный экспорт - только активные магазины
            queryset = ProductInfo.objects.filter(shop__state=True)

        # Применяем фильтры
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        in_stock = request.query_params.get('in_stock')

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        if category_id:
            queryset = queryset.filter(product__category_id=category_id)

        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        if in_stock and in_stock.lower() == 'true':
            queryset = queryset.filter(quantity__gt=0)

        # Выбираем формат экспорта
        export_format = kwargs.get('format', request.query_params.get('format', 'json')).lower()

        # Определяем тип экспорта (простой или расширенный)
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'

        if detailed:
            serializer = ProductExportFullSerializer(queryset, many=True)
        else:
            serializer = ProductExportSerializer(queryset, many=True)

        # Экспорт в зависимости от формата
        if export_format == 'yaml':
            return self.export_yaml(serializer.data, request)
        elif export_format == 'csv':
            return self.export_csv(queryset, request, detailed)
        else:
            return self.export_json(serializer.data, request)

    def export_json(self, data, request):
        """Экспорт в JSON"""
        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="products_export_{timezone.now().date()}.json"'
        return response

    def export_yaml(self, data, request):
        """Экспорт в YAML"""
        yaml_data = yaml.dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )
        response = HttpResponse(yaml_data, content_type='application/x-yaml')
        response['Content-Disposition'] = f'attachment; filename="products_export_{timezone.now().date()}.yaml"'
        return response

    def export_csv(self, queryset, request, detailed=False):
        """Экспорт в CSV"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="products_export_{timezone.now().date()}.csv"'

        writer = csv.writer(response)

        if detailed:
            # Заголовки для расширенного экспорта
            writer.writerow([
                'ID', 'External ID', 'Название товара', 'Категория', 'Модель',
                'Магазин', 'Количество', 'Цена', 'РРЦ', 'Заказано', 'Выручка', 'Параметры'
            ])

            for item in queryset:
                # Собираем параметры в строку
                params = '; '.join([f"{p.parameter.name}: {p.value}" for p in item.product_parameters.all()])

                writer.writerow([
                    item.id,
                    item.external_id,
                    item.product.name,
                    item.product.category.name,
                    item.model,
                    item.shop.name,
                    item.quantity,
                    item.price,
                    item.price_rrc,
                    self.get_total_ordered(item),
                    self.get_revenue(item),
                    params
                ])
        else:
            # Заголовки для простого экспорта
            writer.writerow([
                'ID', 'External ID', 'Название товара', 'Категория', 'Модель',
                'Магазин', 'Количество', 'Цена', 'РРЦ', 'Параметры'
            ])

            for item in queryset:
                # Собираем параметры в строку
                params = '; '.join([f"{p.parameter.name}: {p.value}" for p in item.product_parameters.all()])

                writer.writerow([
                    item.id,
                    item.external_id,
                    item.product.name,
                    item.product.category.name,
                    item.model,
                    item.shop.name,
                    item.quantity,
                    item.price,
                    item.price_rrc,
                    params
                ])

        return response

    def get_total_ordered(self, obj):
        """Вспомогательный метод для подсчета заказов"""
        from django.db.models import Sum
        total = obj.ordered_items.aggregate(total=Sum('quantity'))['total']
        return total or 0

    def get_revenue(self, obj):
        """Вспомогательный метод для подсчета выручки"""
        from django.db.models import Sum, F
        revenue = obj.ordered_items.aggregate(
            total=Sum(F('quantity') * F('product_info__price'))
        )['total']
        return revenue or 0


class AsyncProductExportView(APIView):
    """
    Асинхронный экспорт товаров с использованием Celery

    Позволяет экспортировать большие объемы данных без блокировки сервера.
    Результат экспорта отправляется на email пользователя.

    Пример запроса:
    POST /api/v1/products/export/async/
    {
        "format": "json",
        "shop_id": 1,
        "category_id": 2,
        "min_price": 1000,
        "in_stock": true
    }
    """

    def post(self, request, *args, **kwargs):
        """
        Запуск асинхронного экспорта
        """
        # Проверяем авторизацию
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        # Проверяем формат экспорта
        export_format = request.data.get('format', 'json')
        if export_format not in ['json', 'yaml', 'csv']:
            return JsonResponse({
                'Status': False,
                'Errors': 'Неподдерживаемый формат. Используйте: json, yaml, csv'
            })

        # Собираем фильтры из запроса
        filters = {
            'shop_id': request.data.get('shop_id'),
            'category_id': request.data.get('category_id'),
            'min_price': request.data.get('min_price'),
            'max_price': request.data.get('max_price'),
            'in_stock': request.data.get('in_stock'),
        }
        # Убираем None значения
        filters = {k: v for k, v in filters.items() if v is not None}

        # Проверяем, доступен ли Celery
        try:
            # Запускаем асинхронную задачу
            task = async_export_products.delay(
                user_id=request.user.id,
                export_format=export_format,
                filters=filters
            )

            return JsonResponse({
                'Status': True,
                'Task ID': task.id,
                'Message': 'Экспорт запущен. Результат будет отправлен на email.',
                'Format': export_format,
                'Filters': filters
            })
        except Exception as e:
            return JsonResponse({
                'Status': False,
                'Error': f'Ошибка запуска задачи: {str(e)}. Убедитесь, что Celery worker запущен.'
            }, status=500)

    def get(self, request, *args, **kwargs):
        """
        Проверка статуса асинхронной задачи
        """
        task_id = request.query_params.get('task_id')
        if not task_id:
            return JsonResponse({
                'Status': False,
                'Errors': 'Не указан task_id. Добавьте параметр ?task_id=...'
            })

        try:
            from celery.result import AsyncResult
            task = AsyncResult(task_id)

            if task.ready():
                result = task.result
                if result and result.get('status') == 'success':
                    return JsonResponse({
                        'Status': True,
                        'Ready': True,
                        'Success': True,
                        'Result': result,
                        'Message': f"Экспорт завершен. Файл: {result.get('filename')}"
                    })
                else:
                    return JsonResponse({
                        'Status': True,
                        'Ready': True,
                        'Success': False,
                        'Error': result.get('error', 'Unknown error') if result else 'No result'
                    })
            else:
                return JsonResponse({
                    'Status': True,
                    'Ready': False,
                    'Message': 'Задача еще выполняется. Попробуйте позже.'
                })
        except Exception as e:
            return JsonResponse({
                'Status': False,
                'Error': f'Ошибка проверки статуса: {str(e)}'
            }, status=500)


class DownloadExportFileView(APIView):
    """
    Скачивание файла экспорта

    Пример запроса:
    GET /api/v1/products/export/download/export_user_email_20240101_120000.json
    """

    def get(self, request, filename, *args, **kwargs):
        """
        Скачивание файла по имени
        """
        # Проверяем авторизацию
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        # Безопасность: проверяем, что файл принадлежит пользователю
        user_email_clean = request.user.email.replace('@', '_')
        if not filename.startswith(f'export_{user_email_clean}'):
            return JsonResponse({
                'Status': False,
                'Error': 'Access denied. Этот файл принадлежит другому пользователю.'
            }, status=403)

        # Формируем путь к файлу
        filepath = os.path.join(settings.EXPORT_FILES_ROOT, filename)

        # Проверяем существование файла
        if not os.path.exists(filepath):
            return JsonResponse({
                'Status': False,
                'Error': 'File not found. Возможно, файл был удален (хранится 7 дней).'
            }, status=404)

        # Отдаем файл на скачивание
        try:
            response = FileResponse(
                open(filepath, 'rb'),
                content_type='application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return JsonResponse({
                'Status': False,
                'Error': f'Ошибка при скачивании файла: {str(e)}'
            }, status=500)


# ========== КОНТРОЛЛЕР ДЛЯ ПРОВЕРКИ СТАТУСА CELERY ==========

class CeleryStatusView(APIView):
    """
    Проверка статуса Celery worker
    """

    def get(self, request, *args, **kwargs):
        """
        Проверяет, запущен ли Celery worker
        """
        try:
            from celery.result import AsyncResult
            # Создаем тестовую задачу
            test_task = async_export_products.delay(
                user_id=request.user.id if request.user.is_authenticated else 1,
                export_format='json',
                filters={'test': True}
            )
            # Отменяем тестовую задачу
            test_task.revoke(terminate=True)

            return JsonResponse({
                'Status': True,
                'Celery': 'Running',
                'Message': 'Celery worker активен и готов к работе'
            })
        except Exception as e:
            return JsonResponse({
                'Status': False,
                'Celery': 'Not running',
                'Error': str(e),
                'Message': 'Celery worker не запущен. Запустите: celery -A netology_pd_diplom worker --pool=eventlet -l info'
            }, status=503)


class PublicStatsView(APIView):
    """Публичное API для получения статистики главной страницы"""
    permission_classes = [AllowAny]

    def get(self, request):
        # Количество пользователей (только покупатели, не магазины)
        total_users = User.objects.filter(type='buyer').count()

        # Количество заказов (исключая корзины)
        total_orders = Order.objects.exclude(state='basket').count()

        # Количество товаров
        total_products = ProductInfo.objects.count()

        # Количество активных магазинов
        active_shops = Shop.objects.filter(state=True).count()

        return Response({
            'total_users': total_users,
            'total_orders': total_orders,
            'total_products': total_products,
            'active_shops': active_shops,
        })