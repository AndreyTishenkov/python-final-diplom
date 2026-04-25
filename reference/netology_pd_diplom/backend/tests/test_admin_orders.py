"""
Тестовые сценарии для проверки админки заказов

Запуск тестов:
    python manage.py test backend.tests.test_admin_orders

Или для создания тестовых данных:
    python manage.py shell < backend/tests/test_admin_orders.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')
django.setup()

from backend.models import User, Shop, Category, Product, ProductInfo, Contact, Order, OrderItem
from django.contrib.auth import get_user_model
from django.core.management import call_command


def create_test_data():
    """Создание тестовых данных для проверки админки"""

    print("=" * 60)
    print("Создание тестовых данных для админки заказов")
    print("=" * 60)

    # 1. Создание пользователей
    print("\n1. Создание пользователей...")

    # Покупатели
    buyer1, _ = User.objects.get_or_create(
        email='buyer1@test.ru',
        defaults={
            'first_name': 'Иван',
            'last_name': 'Петров',
            'type': 'buyer',
            'is_active': True,
            'is_staff': False
        }
    )
    if buyer1._state.adding:
        buyer1.set_password('buyer123')
        buyer1.save()
        print(f"   - Создан покупатель: {buyer1.email}")

    buyer2, _ = User.objects.get_or_create(
        email='buyer2@test.ru',
        defaults={
            'first_name': 'Мария',
            'last_name': 'Иванова',
            'type': 'buyer',
            'is_active': True,
            'is_staff': False
        }
    )
    if buyer2._state.adding:
        buyer2.set_password('buyer123')
        buyer2.save()
        print(f"   - Создан покупатель: {buyer2.email}")

    # Магазин
    shop_user, _ = User.objects.get_or_create(
        email='shop@test.ru',
        defaults={
            'first_name': 'Тестовый',
            'last_name': 'Магазин',
            'type': 'shop',
            'is_active': True,
            'is_staff': False
        }
    )
    if shop_user._state.adding:
        shop_user.set_password('shop123')
        shop_user.save()
        print(f"   - Создан магазин: {shop_user.email}")

    # 2. Создание магазина
    print("\n2. Создание магазина...")
    shop, _ = Shop.objects.get_or_create(
        name='ТехноМир',
        defaults={
            'user': shop_user,
            'state': True,
            'url': 'https://technomir.ru'
        }
    )
    print(f"   - Магазин: {shop.name} (ID: {shop.id})")

    # 3. Создание категорий
    print("\n3. Создание категорий...")
    categories = {}
    for cat_data in [
        {'id': 1, 'name': 'Смартфоны'},
        {'id': 2, 'name': 'Ноутбуки'},
        {'id': 3, 'name': 'Планшеты'},
    ]:
        cat, _ = Category.objects.get_or_create(
            id=cat_data['id'],
            defaults={'name': cat_data['name']}
        )
        categories[cat_data['id']] = cat
        cat.shops.add(shop)
        print(f"   - Категория: {cat.name}")

    # 4. Создание товаров
    print("\n4. Создание товаров...")
    products = {}
    products_data = [
        {'id': 1, 'name': 'iPhone 15', 'category_id': 1, 'model': 'A2849', 'price': 99900, 'quantity': 50, 'external_id': 1001},
        {'id': 2, 'name': 'Samsung Galaxy S24', 'category_id': 1, 'model': 'SM-S921B', 'price': 89900, 'quantity': 30, 'external_id': 1002},
        {'id': 3, 'name': 'MacBook Pro 14', 'category_id': 2, 'model': 'MRX33', 'price': 199900, 'quantity': 15, 'external_id': 2001},
        {'id': 4, 'name': 'iPad Pro 11', 'category_id': 3, 'model': 'MNXE3', 'price': 89900, 'quantity': 20, 'external_id': 3001},
    ]

    for prod_data in products_data:
        product, _ = Product.objects.get_or_create(
            id=prod_data['id'],
            defaults={
                'name': prod_data['name'],
                'category_id': prod_data['category_id']
            }
        )
        product_info, _ = ProductInfo.objects.get_or_create(
            external_id=prod_data['external_id'],
            shop=shop,
            defaults={
                'product': product,
                'model': prod_data['model'],
                'price': prod_data['price'],
                'quantity': prod_data['quantity']
            }
        )
        products[prod_data['id']] = product_info
        print(f"   - Товар: {prod_data['name']} ({prod_data['price']} ₽)")

    # 5. Создание контактов
    print("\n5. Создание контактов...")
    contacts = {}

    contact1, _ = Contact.objects.get_or_create(
        user=buyer1,
        defaults={
            'city': 'Москва',
            'street': 'Тверская',
            'house': '15',
            'apartment': '45',
            'phone': '+79161234567'
        }
    )
    contacts[buyer1.id] = contact1
    print(f"   - Контакт для {buyer1.email}: {contact1.city}, {contact1.street}")

    contact2, _ = Contact.objects.get_or_create(
        user=buyer2,
        defaults={
            'city': 'Санкт-Петербург',
            'street': 'Невский',
            'house': '25',
            'apartment': '12',
            'phone': '+79261234567'
        }
    )
    contacts[buyer2.id] = contact2
    print(f"   - Контакт для {buyer2.email}: {contact2.city}, {contact2.street}")

    # 6. Создание заказов в разных статусах
    print("\n6. Создание заказов...")

    orders_data = [
        # Новый заказ
        {
            'user': buyer1,
            'contact': contact1,
            'state': 'new',
            'items': [
                {'product_info': products[1], 'quantity': 1},
                {'product_info': products[3], 'quantity': 2},
            ]
        },
        # Подтвержденный заказ
        {
            'user': buyer2,
            'contact': contact2,
            'state': 'confirmed',
            'items': [
                {'product_info': products[2], 'quantity': 1},
            ]
        },
        # Собранный заказ
        {
            'user': buyer1,
            'contact': contact1,
            'state': 'assembled',
            'items': [
                {'product_info': products[1], 'quantity': 2},
                {'product_info': products[2], 'quantity': 1},
            ]
        },
        # Отправленный заказ
        {
            'user': buyer2,
            'contact': contact2,
            'state': 'sent',
            'items': [
                {'product_info': products[3], 'quantity': 1},
            ]
        },
        # Доставленный заказ
        {
            'user': buyer1,
            'contact': contact1,
            'state': 'delivered',
            'items': [
                {'product_info': products[1], 'quantity': 1},
                {'product_info': products[4], 'quantity': 1},
            ]
        },
        # Отмененный заказ
        {
            'user': buyer2,
            'contact': contact2,
            'state': 'canceled',
            'items': [
                {'product_info': products[2], 'quantity': 1},
            ]
        },
        # Корзина (не оформленный заказ)
        {
            'user': buyer1,
            'contact': None,
            'state': 'basket',
            'items': [
                {'product_info': products[4], 'quantity': 1},
            ]
        },
    ]

    for i, order_data in enumerate(orders_data, 1):
        order, created = Order.objects.get_or_create(
            id=1000 + i,
            defaults={
                'user': order_data['user'],
                'contact': order_data['contact'],
                'state': order_data['state'],
            }
        )

        if created:
            for item_data in order_data['items']:
                OrderItem.objects.create(
                    order=order,
                    product_info=item_data['product_info'],
                    quantity=item_data['quantity']
                )

            # Расчет суммы для отображения
            total = sum(item['quantity'] * item['product_info'].price for item in order_data['items'])
            print(f"   - Заказ #{order.id}: {order_data['state']} (сумма: {total:,.0f} ₽)")
        else:
            print(f"   - Заказ #{order.id} уже существует")

    print("\n" + "=" * 60)
    print("Тестовые данные успешно созданы!")
    print("=" * 60)
    print("\nДля входа в админку:")
    print("   URL: http://localhost:8000/admin/")
    print("   Логин: создайте суперпользователя командой: python manage.py createsuperuser")
    print("\nВ админке вы увидите:")
    print("   - 6 тестовых заказов в разных статусах")
    print("   - Кнопки для изменения статусов")
    print("   - Фильтры для поиска")
    print("")


def check_admin_urls():
    """Проверка доступности URL админки"""
    print("\n" + "=" * 60)
    print("Проверка URL админки")
    print("=" * 60)

    from django.test import Client
    from django.urls import reverse

    client = Client()

    # Создаем суперпользователя для тестов
    User = get_user_model()
    admin_user, created = User.objects.get_or_create(
        email='admin@test.ru',
        defaults={
            'is_superuser': True,
            'is_staff': True,
            'is_active': True,
            'first_name': 'Admin',
            'last_name': 'Test'
        }
    )
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        print("   - Создан тестовый администратор: admin@test.ru / admin123")

    # Проверка логина
    client.login(username='admin@test.ru', password='admin123')

    # Проверка основных URL
    urls_to_check = [
        ('admin:index', '/admin/'),
        ('admin:backend_order_changelist', '/admin/backend/order/'),
        ('admin:backend_user_changelist', '/admin/backend/user/'),
        ('admin:backend_shop_changelist', '/admin/backend/shop/'),
        ('admin:backend_product_changelist', '/admin/backend/product/'),
    ]

    print("\nПроверка URL:")
    for name, url in urls_to_check:
        try:
            if name == 'admin:index':
                response = client.get('/admin/')
            else:
                response = client.get(url)

            if response.status_code == 200:
                print(f"   - OK: {url}")
            else:
                print(f"   - ERROR: {url} (статус: {response.status_code})")
        except Exception as e:
            print(f"   - ERROR: {url} ({str(e)})")


def print_test_scenarios():
    """Вывод сценариев для ручного тестирования"""

    print("\n" + "=" * 60)
    print("Сценарии для проверки админки заказов")
    print("=" * 60)

    scenarios = [
        {
            "name": "Проверка списка заказов",
            "steps": [
                "1. Зайдите в админку: http://localhost:8000/admin/",
                "2. Нажмите на раздел 'Orders'",
                "3. Проверьте, что отображаются все 6 заказов",
                "4. Проверьте цветные индикаторы статусов",
                "5. Проверьте отображение суммы каждого заказа"
            ]
        },
        {
            "name": "Проверка фильтрации",
            "steps": [
                "1. В разделе Orders, справа выберите фильтр 'State'",
                "2. Выберите 'new' - должны показаться только новые заказы",
                "3. Выберите 'confirmed' - должны показаться подтвержденные",
                "4. Сбросьте фильтр"
            ]
        },
        {
            "name": "Проверка поиска",
            "steps": [
                "1. В поле поиска введите email: buyer1@test.ru",
                "2. Должны показаться заказы этого покупателя",
                "3. Введите ID заказа: 1001",
                "4. Должен найтись конкретный заказ"
            ]
        },
        {
            "name": "Изменение статуса заказа",
            "steps": [
                "1. Найдите заказ со статусом 'new' (ID: 1001)",
                "2. Нажмите кнопку 'Подтвердить'",
                "3. Проверьте, что статус изменился на 'confirmed'",
                "4. Нажмите кнопку 'Собрать'",
                "5. Нажмите 'Отправить'",
                "6. Нажмите 'Доставить'",
                "7. Убедитесь, что покупатель получил email уведомления"
            ]
        },
        {
            "name": "Отмена заказа",
            "steps": [
                "1. Найдите заказ со статусом 'new' (ID: 1001)",
                "2. Нажмите кнопку 'Отменить'",
                "3. Проверьте, что статус изменился на 'canceled'"
            ]
        },
        {
            "name": "Просмотр деталей заказа",
            "steps": [
                "1. Нажмите на ID любого заказа",
                "2. Проверьте отображение:",
                "   - Информации о покупателе",
                "   - Контактных данных",
                "   - Состава заказа с ценами",
                "3. Измените статус через выпадающий список",
                "4. Нажмите 'Save'"
            ]
        },
        {
            "name": "Массовые операции",
            "steps": [
                "1. Отметьте чекбоксы у 2-3 заказов",
                "2. В выпадающем списке 'Action' выберите 'Подтвердить выбранные заказы'",
                "3. Нажмите 'Go'",
                "4. Проверьте, что статусы изменились"
            ]
        },
        {
            "name": "Отправка уведомления",
            "steps": [
                "1. Найдите любой заказ (не корзину)",
                "2. Нажмите кнопку 'Отправить уведомление'",
                "3. Проверьте, что на email покупателя пришло письмо"
            ]
        }
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n--- Сценарий {i}: {scenario['name']} ---")
        for step in scenario['steps']:
            print(f"   {step}")
        print()


def run_all_checks():
    """Запуск всех проверок"""
    create_test_data()
    # check_admin_urls()
    print_test_scenarios()

    print("\n" + "=" * 60)
    print("Для входа в админку выполните:")
    print("   1. python manage.py createsuperuser (если еще нет)")
    print("   2. python manage.py runserver")
    print("   3. Откройте http://localhost:8000/admin/")
    print("=" * 60)


if __name__ == '__main__':
    run_all_checks()