#!/usr/bin/env python
"""
===============================================================================
ТЕСТОВЫЙ ДЕМОНСТРАЦИОННЫЙ ФАЙЛ ДЛЯ АДМИНКИ ЗАКАЗОВ
===============================================================================

Данный скрипт создает тестовые данные для проверки функционала админки заказов.

Что проверяется:
1. Создание заказов с разными статусами
2. Отображение заказов в админ-панели
3. Возможность изменения статусов через кнопки
4. Отправка email уведомлений при смене статуса
5. Фильтрация и поиск заказов

Как запустить:
    python test_orders_demo.py

После запуска:
1. Зайдите в админку: http://localhost:8000/admin/
2. Используйте логин: admin@demo.ru / admin123
3. Перейдите в раздел "Orders"
4. Проверьте созданные заказы

Автор: Дипломный проект
Дата: 2024
===============================================================================
"""

import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')
django.setup()

from backend.models import User, Shop, Category, Product, ProductInfo, Contact, Order, OrderItem
from django.core.management import call_command


def print_header(title):
    """Печать заголовка"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_success(message):
    """Печать успешного сообщения"""
    print(f"OK! -> {message}")


def print_error(message):
    """Печать сообщения об ошибке"""
    print(f"ERROR! -> {message}")


def print_info(message):
    """Печать информационного сообщения"""
    print(f"Attention! -> {message}")


def create_superuser():
    """Создание суперпользователя для доступа к админке"""
    print_header("1. СОЗДАНИЕ СУПЕРПОЛЬЗОВАТЕЛЯ")

    admin_email = 'admin@demo.ru'
    admin_password = 'admin123'

    user, created = User.objects.get_or_create(
        email=admin_email,
        defaults={
            'first_name': 'Администратор',
            'last_name': 'Демо',
            'is_superuser': True,
            'is_staff': True,
            'is_active': True,
            'type': 'buyer'
        }
    )

    if created:
        user.set_password(admin_password)
        user.save()
        print_success(f"Создан суперпользователь: {admin_email} / {admin_password}")
    else:
        # Обновляем пароль на всякий случай
        user.set_password(admin_password)
        user.save()
        print_info(f"Суперпользователь уже существует: {admin_email}")
        print_info(f"Используйте пароль: {admin_password}")

    return user


def create_test_shop():
    """Создание тестового магазина"""
    print_header("2. СОЗДАНИЕ ТЕСТОВОГО МАГАЗИНА")

    # Создаем пользователя-магазин
    shop_user, _ = User.objects.get_or_create(
        email='test_shop@demo.ru',
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
        print_success(f"Создан пользователь магазина: {shop_user.email}")

    # Создаем магазин
    shop, created = Shop.objects.get_or_create(
        name='Демо Магазин',
        defaults={
            'user': shop_user,
            'state': True,
            'url': 'https://demo-shop.ru'
        }
    )

    if created:
        print_success(f"Создан магазин: {shop.name} (ID: {shop.id})")
    else:
        print_info(f"Магазин уже существует: {shop.name}")

    return shop


def create_categories(shop):
    """Создание категорий товаров"""
    print_header("3. СОЗДАНИЕ КАТЕГОРИЙ")

    categories_data = [
        {'id': 1, 'name': 'Смартфоны'},
        {'id': 2, 'name': 'Ноутбуки'},
        {'id': 3, 'name': 'Планшеты'},
        {'id': 4, 'name': 'Аксессуары'},
    ]

    categories = {}
    for cat_data in categories_data:
        cat, created = Category.objects.get_or_create(
            id=cat_data['id'],
            defaults={'name': cat_data['name']}
        )
        cat.shops.add(shop)
        categories[cat_data['id']] = cat
        if created:
            print_success(f"Создана категория: {cat.name}")
        else:
            print_info(f"Категория уже существует: {cat.name}")

    return categories


def create_products(shop, categories):
    """Создание тестовых товаров"""
    print_header("4. СОЗДАНИЕ ТОВАРОВ")

    products_data = [
        {
            'id': 1, 'name': 'iPhone 15 Pro', 'category_id': 1,
            'model': 'A2848', 'price': 99900, 'price_rrc': 109900,
            'quantity': 50, 'external_id': 1001
        },
        {
            'id': 2, 'name': 'Samsung Galaxy S24', 'category_id': 1,
            'model': 'SM-S921B', 'price': 89900, 'price_rrc': 99900,
            'quantity': 30, 'external_id': 1002
        },
        {
            'id': 3, 'name': 'MacBook Pro 14', 'category_id': 2,
            'model': 'MRX33', 'price': 199900, 'price_rrc': 229900,
            'quantity': 15, 'external_id': 2001
        },
        {
            'id': 4, 'name': 'iPad Pro 11', 'category_id': 3,
            'model': 'MNXE3', 'price': 89900, 'price_rrc': 99900,
            'quantity': 20, 'external_id': 3001
        },
        {
            'id': 5, 'name': 'AirPods Pro', 'category_id': 4,
            'model': 'MTJV3', 'price': 24990, 'price_rrc': 29990,
            'quantity': 100, 'external_id': 4001
        },
    ]

    products = {}
    for prod_data in products_data:
        product, _ = Product.objects.get_or_create(
            id=prod_data['id'],
            defaults={
                'name': prod_data['name'],
                'category_id': prod_data['category_id']
            }
        )

        product_info, created = ProductInfo.objects.get_or_create(
            external_id=prod_data['external_id'],
            shop=shop,
            defaults={
                'product': product,
                'model': prod_data['model'],
                'price': prod_data['price'],
                'price_rrc': prod_data['price_rrc'],
                'quantity': prod_data['quantity']
            }
        )
        products[prod_data['id']] = product_info
        if created:
            print_success(f"Создан товар: {prod_data['name']} - {prod_data['price']} ₽")
        else:
            print_info(f"Товар уже существует: {prod_data['name']}")

    return products


def create_test_buyer():
    """Создание тестового покупателя"""
    print_header("5. СОЗДАНИЕ ПОКУПАТЕЛЯ")

    buyer, created = User.objects.get_or_create(
        email='buyer@demo.ru',
        defaults={
            'first_name': 'Иван',
            'last_name': 'Петров',
            'type': 'buyer',
            'is_active': True,
            'is_staff': False
        }
    )

    if created:
        buyer.set_password('buyer123')
        buyer.save()
        print_success(f"Создан покупатель: {buyer.email} / buyer123")
    else:
        print_info(f"Покупатель уже существует: {buyer.email}")

    return buyer


def create_contact(buyer):
    """Создание контакта покупателя"""
    print_header("6. СОЗДАНИЕ КОНТАКТА")

    contact, created = Contact.objects.get_or_create(
        user=buyer,
        defaults={
            'city': 'Москва',
            'street': 'Тверская',
            'house': '15',
            'apartment': '45',
            'phone': '+79161234567'
        }
    )

    if created:
        print_success(f"Создан контакт: {contact.city}, ул. {contact.street}")
    else:
        print_info(f"Контакт уже существует: {contact.city}, ул. {contact.street}")

    return contact


def create_orders(buyer, contact, products):
    """Создание заказов с разными статусами"""
    print_header("7. СОЗДАНИЕ ТЕСТОВЫХ ЗАКАЗОВ")

    orders_data = [
        {
            'state': 'new',
            'description': 'Новый заказ - ожидает подтверждения',
            'items': [(products[1], 1), (products[4], 2)]
        },
        {
            'state': 'confirmed',
            'description': 'Подтвержденный заказ - ожидает сборки',
            'items': [(products[2], 1)]
        },
        {
            'state': 'assembled',
            'description': 'Собранный заказ - ожидает отправки',
            'items': [(products[1], 2), (products[2], 1)]
        },
        {
            'state': 'sent',
            'description': 'Отправленный заказ - в пути',
            'items': [(products[3], 1)]
        },
        {
            'state': 'delivered',
            'description': 'Доставленный заказ - завершен',
            'items': [(products[1], 1), (products[5], 1)]
        },
        {
            'state': 'canceled',
            'description': 'Отмененный заказ',
            'items': [(products[2], 1)]
        },
    ]

    created_orders = []
    start_id = 1000

    for i, order_data in enumerate(orders_data, 1):
        order_id = start_id + i

        # Удаляем старый заказ с таким ID, если существует
        Order.objects.filter(id=order_id).delete()

        # Создаем новый заказ
        order = Order.objects.create(
            id=order_id,
            user=buyer,
            contact=contact,
            state=order_data['state']
        )

        # Добавляем товары
        total_sum = 0
        for product, quantity in order_data['items']:
            OrderItem.objects.create(
                order=order,
                product_info=product,
                quantity=quantity
            )
            total_sum += product.price * quantity

        created_orders.append(order)
        print_success(f"Заказ #{order.id}: {order_data['description']}")
        print_info(f"   Сумма: {total_sum:,} ₽, Товаров: {len(order_data['items'])}")

    return created_orders


def print_admin_instructions():
    """Инструкция для работы с админкой"""
    print_header("8. ИНСТРУКЦИЯ ПО РАБОТЕ С АДМИНКОЙ")

    instructions = """
    ЧТО МОЖНО СДЕЛАТЬ В АДМИНКЕ:
    ===============================================================================
    
    1. ПРОСМОТР ЗАКАЗОВ:
       - Зайдите в раздел "Список заказов"
       - Вы увидите таблицу со всеми заказами
       - Каждый заказ имеет цветной статус
       - Сумма заказа рассчитана автоматически
    
    2. ИЗМЕНЕНИЕ СТАТУСА ЗАКАЗА (через кнопки в списке):
       - Для заказа "Новый" → кнопки "Подтвердить" / "Отменить"
       - Для заказа "Подтвержден" → кнопки "Собрать" / "Отменить"
       - Для заказа "Собран" → кнопка "Отправить"
       - Для заказа "Отправлен" → кнопка "Доставить"
       - Для любого заказа → кнопка "Отправить уведомление"
    
    3. ПРОСМОТР ДЕТАЛЕЙ ЗАКАЗА:
       - Нажмите на ID заказа
       - Вы увидите полную информацию:
         * Данные покупателя
         * Адрес доставки
         * Список товаров с ценами
         * Общую сумму
    
    4. ФИЛЬТРАЦИЯ:
       - Справа есть фильтр по статусу заказа
       - Фильтр по дате создания
       - Поиск по ID, email, телефону
    
    5. МАССОВЫЕ ОПЕРАЦИИ:
       - Выберите несколько заказов (чекбоксы)
       - Выберите действие в выпадающем списке
       - Нажмите "Go"
    
    6. ОТПРАВКА УВЕДОМЛЕНИЙ:
       - При изменении статуса EMAIL отправляется АВТОМАТИЧЕСКИ
       - Можно отправить вручную кнопкой "Отправить уведомление"
    """

    print(instructions)


def print_test_results():
    """Вывод результатов теста"""
    print_header("9. РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")

    stats = {
        'users': User.objects.count(),
        'shops': Shop.objects.count(),
        'categories': Category.objects.count(),
        'products': ProductInfo.objects.count(),
        'contacts': Contact.objects.count(),
        'orders': Order.objects.count(),
        'order_items': OrderItem.objects.count(),
    }

    print("СТАТИСТИКА СОЗДАННЫХ ДАННЫХ:")
    print(f"   - Пользователей: {stats['users']}")
    print(f"   - Магазинов: {stats['shops']}")
    print(f"   - Категорий: {stats['categories']}")
    print(f"   - Товаров: {stats['products']}")
    print(f"   - Контактов: {stats['contacts']}")
    print(f"   - Заказов: {stats['orders']}")
    print(f"   - Позиций в заказах: {stats['order_items']}")

    print("\nСПИСОК ЗАКАЗОВ:")
    for order in Order.objects.all().order_by('id'):
        total = sum(item.quantity * item.product_info.price for item in order.ordered_items.all())
        status_names = {
            'new': 'Новый',
            'confirmed': 'Подтвержден',
            'assembled': 'Собран',
            'sent': 'Отправлен',
            'delivered': 'Доставлен',
            'canceled': 'Отменен',
            'basket': 'Корзина'
        }
        status_display = status_names.get(order.state, order.state)
        print(f"   - Заказ #{order.id}: {status_display} | Сумма: {total:,.0f} ₽")


def print_final_instructions():
    """Финальные инструкции"""
    print_header("10. КАК ПРОВЕРИТЬ РАБОТУ АДМИНКИ")

    final = """
    ДЛЯ ПРОВЕРКИ ВЫПОЛНИТЕ СЛЕДУЮЩИЕ ШАГИ:
    ===============================================================================
    
    1. ЗАПУСТИТЕ СЕРВЕР (если не запущен):
       python manage.py runserver
    
    2. ОТКРОЙТЕ АДМИНКУ В БРАУЗЕРЕ:
       http://localhost:8000/admin/
    
    3. ВОЙДИТЕ С УЧЕТНЫМИ ДАННЫМИ:
       Email: admin@demo.ru
       Пароль: admin123
    
    4. ПРОВЕРЬТЕ ОСНОВНОЙ ФУНКЦИОНАЛ:
       Перейдите в раздел "Список заказов" - должны быть видны все заказы
       Нажмите на кнопку "Подтвердить" у заказа со статусом "Новый"
       Проверьте, что статус изменился и пришло email уведомление
       Нажмите на ID заказа - проверьте детальную информацию
       Используйте фильтры и поиск
    
    5. ПРОВЕРЬТЕ ОТПРАВКУ EMAIL (опционально):
       - При изменении статуса автоматически отправляется письмо
       - Письмо приходит на email покупателя (buyer@demo.ru)
       - Можно проверить в почтовом ящике или логах сервера
    
    ===============================================================================
    ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!
    """

    print(final)


def main():
    """Главная функция"""
    header="""===============================================================================
     ТЕСТОВЫЙ ДЕМОНСТРАЦИОННЫЙ ФАЙЛ ДЛЯ АДМИНКИ ЗАКАЗОВ
==============================================================================="""

    print(header)
    print_info("Начинаю создание тестовых данных...")

    try:
        # Создаем все необходимые данные
        admin = create_superuser()
        shop = create_test_shop()
        categories = create_categories(shop)
        products = create_products(shop, categories)
        buyer = create_test_buyer()
        contact = create_contact(buyer)
        orders = create_orders(buyer, contact, products)

        # Выводим результаты
        print_test_results()
        print_admin_instructions()
        print_final_instructions()

        print("\n" + "=" * 70)
        print("ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!")
        print("=" * 70)

    except Exception as e:
        print_error(f"Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()


def run():
    """Главная функция для запуска через управляющую команду"""
    header = "ТЕСТОВЫЙ ДЕМОНСТРАЦИОННЫЙ ФАЙЛ ДЛЯ АДМИНКИ ЗАКАЗОВ"
    print_header(header)
    print_info("Начинаю создание тестовых данных...\n")

    try:
        admin = create_superuser()
        shop = create_test_shop()
        categories = create_categories(shop)
        products = create_products(shop, categories)
        buyer = create_test_buyer()
        contact = create_contact(buyer)
        orders = create_orders(buyer, contact, products)

        print_test_results()
        print_admin_instructions()

        print("\n" + "=" * 70)
        print(" КАК ПРОВЕРИТЬ:")
        print("=" * 70)
        print("1. Запустите сервер: python manage.py runserver")
        print("2. Откройте: http://localhost:8000/admin/")
        print("3. Войдите: admin@demo.ru / admin123")
        print("4. Нажмите на 'Список заказов'")
        print("\n ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!")
        print("=" * 70)

    except Exception as e:
        print_error(f"Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()