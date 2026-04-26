from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse, FileResponse

from requests import get

from rest_framework.request import Request
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.parsers import MultiPartParser, FormParser

from ujson import loads as load_json

from yaml import load as load_yaml, Loader

import json, csv, os, logging, sentry_sdk

from datetime import datetime  # Добавлен для работы с датами

from django.utils import timezone
from django.shortcuts import render

from backend.tasks import (
    async_import_products, async_update_price_list, send_order_status_email
)

from backend.models import (
    Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
    Order, OrderItem, Contact, ConfirmEmailToken, User, ProductImage
)

from backend.serializers import (
    UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer,
    OrderItemSerializer, OrderSerializer, ContactSerializer, ProductExportSerializer,
    ProductExportFullSerializer, UserAvatarSerializer, ProductMainImageSerializer,
    ProductImageSerializer
)

from backend.signals import new_user_registered, new_order

from backend.throttles import (
    RegisterThrottle, LoginThrottle, ExportThrottle,
    ImportThrottle, BasketThrottle, OrderThrottle
)

from backend.image_processing import (
    process_user_avatar, process_product_main_image, process_product_gallery_images
)

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


logger = logging.getLogger(__name__)

def index(request):
    """ Главная страница магазина """
    return render(request, 'index.html')

def admin_dashboard(request):
    """Дашборд для админки"""
    return render(request, 'admin/dashboard.html')


class UserAvatarUploadView(APIView):
    """
    Загрузка аватара пользователя с асинхронной обработкой
    """
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется вход в систему.'}, status=403)

        serializer = UserAvatarSerializer(request.user, data=request.data, partial=True)

        if serializer.is_valid():
            # Сохраняем аватар
            serializer.save()

            # Запускаем асинхронную обработку
            if request.user.avatar:
                process_user_avatar.delay(request.user.id, request.user.avatar.path)

            return JsonResponse({
                'Status': True,
                'Message': 'Аватар загружен. Началась обработка.',
                'Data': serializer.data
            })

        return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)

    def get(self, request):
        """Получение аватара пользователя"""
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется вход в систему.'}, status=403)

        serializer = UserAvatarSerializer(request.user)
        return Response(serializer.data)


class ProductMainImageUploadView(APIView):
    """
    Загрузка главного изображения товара
    """
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, product_id, *args, **kwargs):
        # Проверка прав (только для магазинов)
        if not request.user.is_authenticated or request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Доступ запрещен.'}, status=403)

        try:
            product = Product.objects.get(id=product_id, shop__user_id=request.user.id)
        except Product.DoesNotExist:
            return JsonResponse({'Status': False, 'Error': 'Товар не найден.'}, status=404)

        serializer = ProductMainImageSerializer(product, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            if product.main_image:
                process_product_main_image.delay(product.id, product.main_image.path)

            return JsonResponse({
                'Status': True,
                'Message': 'Изображение загружено. Началась обработка.',
                'Data': serializer.data
            })

        return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)


class ProductGalleryImageView(APIView):
    """
    Загрузка дополнительных изображений товара
    """
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, product_id, *args, **kwargs):
        if not request.user.is_authenticated or request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Доступ запрещен.'}, status=403)

        try:
            product = Product.objects.get(id=product_id, shop__user_id=request.user.id)
        except Product.DoesNotExist:
            return JsonResponse({'Status': False, 'Error': 'Товар не найден.'}, status=404)

        serializer = ProductImageSerializer(data=request.data)

        if serializer.is_valid():
            product_image = serializer.save(product=product)

            if product_image.image:
                process_product_gallery_images.delay(product_image.id)

            return JsonResponse({
                'Status': True,
                'Message': 'Изображение загружено. Началась обработка.',
                'Data': serializer.data
            })

        return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)

    def get(self, request, product_id):
        """Получение всех изображений товара"""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'Status': False, 'Error': 'Товар не найден.'}, status=404)

        images = product.images.all()
        serializer = ProductImageSerializer(images, many=True)
        return Response(serializer.data)


class RegisterAccount(APIView):
    """
    Регистрация нового пользователя.

    Создаёт нового пользователя с ролью 'покупатель'.
    На указанный email отправляется токен подтверждения.

    Параметры запроса:
    - first_name (str): Имя пользователя
    - last_name (str): Фамилия пользователя
    - email (str): Email (используется как логин)
    - password (str): Пароль (должен быть сложным)
    - company (str): Компания (необязательно)
    - position (str): Должность (необязательно)

    Ответ:
    - Status (bool): Успех операции
    - Errors (dict): Ошибки валидации (при неудаче)

    Ограничение: не более 5 регистраций в час с одного IP.
    """

    throttle_classes = [RegisterThrottle]

    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST‑запрос и создаёт нового пользователя.
        Аргументы:
            - request (Request): Объект запроса Django.
        Возвращает:
            - JsonResponse: Ответ, содержащий статус выполнения операции и возможные ошибки.
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
        Аргументы:
            - request (Request): Объект запроса Django.
        Возвращает:
            - JsonResponse: Ответ, содержащий статус выполнения операции и возможные ошибки.
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
    Класс для управления данными учётной записи пользователя.
    Методы:
        - get: Получить данные аутентифицированного пользователя.
        - post: Обновить данные учётной записи аутентифицированного пользователя.
    Атрибуты:
        - None
    """

    # получить данные
    def get(self, request: Request, *args, **kwargs):
        """
        Получить данные аутентифицированного пользователя.
        Аргументы:
            - request (Request): Объект запроса Django.
        Возвращает:
            - Response: Ответ, содержащий данные аутентифицированного пользователя.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Редактирование методом POST
    def post(self, request, *args, **kwargs):
        """
        Обновить данные учётной записи аутентифицированного пользователя.
        Аргументы:
            - request (Request): Объект запроса Django.
        Возвращает:
            - JsonResponse: Ответ, содержащий статус выполнения операции и возможные ошибки.
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
    Авторизация пользователя.

    Возвращает токен для аутентификации в последующих запросах.

    Параметры запроса:
    - email (str): Email пользователя
    - password (str): Пароль

    Ответ при успехе:
    - Status (bool): true
    - Token (str): Токен авторизации

    Ответ при ошибке:
    - Status (bool): false
    - Errors (str): Описание ошибки

    Ограничение: не более 10 попыток в час с одного IP для одного email.
    """

    throttle_classes = [LoginThrottle]

    @extend_schema(
        summary="Авторизация пользователя",
        description="Авторизует пользователя и возвращает токен для последующих запросов",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'format': 'email'},
                    'password': {'type': 'string', 'format': 'password'},
                },
                'required': ['email', 'password']
            }
        },
        responses={
            200: OpenApiResponse(description='Успешная авторизация', response={
                'type': 'object',
                'properties': {
                    'Status': {'type': 'boolean'},
                    'Token': {'type': 'string'},
                }
            }),
            401: OpenApiResponse(description='Ошибка авторизации'),
        }
    )

    # Авторизация методом POST
    def post(self, request, *args, **kwargs):
        """
        Аутентификация пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: статус операции и ошибки (если есть).
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
    Просмотр товаров с фильтрацией.

    Параметры фильтрации:
    - shop_id (int): ID магазина
    - category_id (int): ID категории
    - min_price (int): Минимальная цена
    - max_price (int): Максимальная цена
    - in_stock (bool): Только товары в наличии

    Возвращает список товаров с параметрами.

    Доступные методы:
        - get: Возвращает информацию о товарах с применением указанных фильтров.
    Атрибуты:
        - None
    """

    @extend_schema(
        summary="Получить список товаров",
        description="Возвращает список товаров с возможностью фильтрации по магазину, категории и цене",
        parameters=[
            OpenApiParameter(name='shop_id', description='ID магазина', required=False, type=int),
            OpenApiParameter(name='category_id', description='ID категории', required=False, type=int),
            OpenApiParameter(name='min_price', description='Минимальная цена', required=False, type=int),
            OpenApiParameter(name='max_price', description='Максимальная цена', required=False, type=int),
            OpenApiParameter(name='in_stock', description='Только товары в наличии', required=False, type=bool),
        ],
        responses={
            200: ProductInfoSerializer(many=True),
            400: OpenApiResponse(description='Неверные параметры запроса'),
        }
    )

    def get(self, request: Request, *args, **kwargs):
        """
        Получить данные о товарах по фильтрам.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - Response: ответ с информацией о товарах.
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
    Управление корзиной пользователя.

    Формат данных для POST:
    {
        "items": "[{\"product_info\": 1, \"quantity\": 2}]"
    }

    Методы:
        - get: Получить товары в корзине пользователя.
        - post: Добавить товар в корзину пользователя.
        - put: Обновить количество товара в корзине пользователя.
        - delete: Удалить товар из корзины пользователя.
    Атрибуты:
        - None

    Ограничение: не более 200 операций в час.
    """

    throttle_classes = [BasketThrottle]

    # получить корзину
    def get(self, request, *args, **kwargs):
        """
        Получить список товаров в корзине пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - Response: ответ с перечнем товаров в корзине.
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
        Добавить товары в корзину пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: ответ со статусом операции и ошибками (при наличии).
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
        Удалить товары из корзины пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: ответ со статусом операции и ошибками (при наличии).
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
        Обновить товары в корзине пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: ответ со статусом операции и ошибками (при наличии).
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
    Класс обновления информации о партнёре.
    Методы:
        - post: Обновление данных партнёра.
    Атрибуты:
        - None

    Ограничение: наследует стандартное ограничение для пользователей.
    """

    # Использует стандартный UserRateThrottle
    throttle_classes = [UserRateThrottle]

    def post(self, request, *args, **kwargs):
        """
        Обновить прайс‑лист партнёра.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: ответ со статусом операции и ошибками (при наличии).
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
    Класс управления статусом партнёра.
    Методы:
        - get: Получение статуса партнёра.
    Атрибуты:
       - None
    """
    # получить текущий статус
    def get(self, request, *args, **kwargs):
        """
        Получить состояние партнёра.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - Response: ответ с информацией о состоянии партнёра.
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
        Обновляет статус партнёра.
        Параметры:
            - request (Request): запрос Django.
        Возвращаемое значение:
            - JsonResponse: ответ с указанием статуса операции и возможных ошибок.
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
    Методы:
        - get: Получение заказов авторизованного партнёра.
    Атрибуты:
        - None
    """

    def get(self, request, *args, **kwargs):
        """
        Получить заказы авторизованного партнёра.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - Response: ответ с перечнем заказов партнёра.
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
    Класс для управления контактной информацией.
    Методы:
        - get: Получить контактную информацию авторизованного пользователя.
        - post: Создать новый контакт для авторизованного пользователя.
        - put: Обновить контактную информацию авторизованного пользователя.
        - delete: Удалить контакт авторизованного пользователя.
    Атрибуты:
       - None
    """

    # получить мои контакты
    def get(self, request, *args, **kwargs):
        """
        Получить контакты авторизованного пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - Response: ответ с контактной информацией пользователя.
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
        Создать контакт для авторизованного пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: ответ со статусом операции и ошибками (при наличии).
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
        Удалить контакт пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: ответ со статусом операции и ошибками (при наличии).
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
            Обновить контакты авторизованного пользователя.
            Входные данные:
                - request (Request): запрос Django.
            Выходные данные:
                - JsonResponse: ответ со статусом операции и ошибками (при наличии). 
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
    Методы:
        - get: Получить сведения о конкретном заказе.
        - post: Создать новый заказ.
        - put: Обновить сведения о конкретном заказе.
        - delete: Удалить конкретный заказ.
    Атрибуты:
        - None

    Ограничение: не более 50 заказов в час.
    """

    throttle_classes = [OrderThrottle]

    # получить мои заказы
    def get(self, request, *args, **kwargs):
        """
        Получить данные о заказах пользователя.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - Response: ответ с информацией о заказах.
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
        Оформить заказ и отправить уведомление.
        Входные данные:
            - request (Request): запрос Django.
        Выходные данные:
            - JsonResponse: ответ со статусом операции и ошибками (при наличии).
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

        if is_updated:
            # Асинхронная отправка вместо синхронного сигнала
            new_order.send(sender=self.__class__, user_id=request.user.id, order_id=request.data['id'])
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

    Ограничение: не более 20 экспортов в час.
    """

    throttle_classes = [ExportThrottle]

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

    Ограничение: не более 20 экспортов в час.
    """

    throttle_classes = [ExportThrottle]

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


# Класс для проверки статуса Celery
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


class AsyncImportView(APIView):
    """
    Асинхронный импорт товаров из YAML

    Ограничение: не более 5 импортов в час.
    """

    throttle_classes = [ImportThrottle]

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        yaml_content = request.data.get('yaml_content')
        if not yaml_content:
            return JsonResponse({'Status': False, 'Error': 'Не указано содержимое YAML'})

        task = async_import_products.delay(
            user_id=request.user.id,
            yaml_content=yaml_content,
            shop_name=request.data.get('shop_name')
        )

        return JsonResponse({
            'Status': True,
            'Task ID': task.id,
            'Message': 'Импорт запущен. Результат придет на email.'
        })


class AsyncUpdatePriceListView(APIView):
    """Асинхронное обновление прайс-листа"""

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if not url:
            return JsonResponse({'Status': False, 'Error': 'Не указан URL'})

        task = async_update_price_list.delay(
            user_id=request.user.id,
            url=url
        )

        return JsonResponse({
            'Status': True,
            'Task ID': task.id,
            'Message': 'Обновление прайс-листа запущено. Результат придет на email.'
        })

def strtobool(val):
    # Преобразуем входящее строковое представления булевых значений
    if isinstance(val, bool):
        return val

    val_str = str(val).lower().strip()

    if val_str in ('y', 'yes', 't', 'true', 'on', '1', '1.0', 'ok', 'enable', 'enabled'):
        return True
    elif val_str in ('n', 'no', 'f', 'false', 'off', '0', '0.0', 'disable', 'disabled', 'none'):
        return False
    else:
        raise ValueError(f"Invalid boolean value: {val}")


class TestErrorView(APIView):
    """
    Тестовый эндпоинт для проверки работы Sentry.

    Различные типы ошибок для демонстрации:
    - ZeroDivisionError: /error/zero/
    - ValueError: /error/value/
    - KeyError: /error/key/
    - IndexError: /error/index/
    - Custom exception: /error/custom/
    """
    permission_classes = [AllowAny]

    def get(self, request, error_type='zero'):
        """
        Генерирует различные типы исключений для тестирования Sentry.

        Параметры:
        - error_type: zero, value, key, index, custom, log, warning
        """

        if error_type == 'zero':
            # Деление на ноль
            result = 1 / 0
            return Response({'result': result})

        elif error_type == 'value':
            # Ошибка значения
            int('not_a_number')
            return Response({'success': True})

        elif error_type == 'key':
            # Отсутствующий ключ в словаре
            data = {'name': 'Test'}
            value = data['nonexistent_key']
            return Response({'value': value})

        elif error_type == 'index':
            # Индекс вне диапазона
            items = [1, 2, 3]
            value = items[10]
            return Response({'value': value})

        elif error_type == 'custom':
            # Пользовательское исключение
            raise Exception('Это тестовое исключение для Sentry!')

        elif error_type == 'log':
            # Отправка сообщения в Sentry без исключения
            try:
                raise ValueError('Тестовое бизнес-исключение')
            except Exception as e:
                sentry_sdk.capture_exception(e)
                return Response({
                    'status': 'error',
                    'message': 'Ошибка залогирована в Sentry',
                    'error_type': type(e).__name__
                })

        elif error_type == 'warning':
            # Отправка предупреждения в Sentry
            sentry_sdk.capture_message('Тестовое предупреждение из API', level='warning')
            return Response({
                'status': 'warning',
                'message': 'Предупреждение отправлено в Sentry'
            })

        else:
            return Response({
                'message': 'Тестовый эндпоинт для Sentry',
                'available_error_types': ['zero', 'value', 'key', 'index', 'custom', 'log', 'warning'],
                'example': '/api/v1/test-error/zero/'
            })


class DatabaseErrorView(APIView):
    """
    Тест ошибки базы данных
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from django.db import connection

        # Выполняем несуществующий SQL запрос
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM nonexistent_table_12345")

        return Response({'status': 'ok'})


class PerformanceTestView(APIView):
    """
    Тест производительности для Sentry (медленный запрос)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        import time

        # Симулируем медленную операцию
        time.sleep(2)

        return Response({
            'status': 'ok',
            'message': 'Медленный запрос (2 секунды) - Sentry должен зафиксировать'
        })