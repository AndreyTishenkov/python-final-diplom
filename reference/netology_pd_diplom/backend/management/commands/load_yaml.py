import yaml
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, User

class Command(BaseCommand):
    help = 'Загружает данные из YAML-файла в базу данных'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Путь к YAML файлу')
        parser.add_argument('--user', type=int, help='ID пользователя (владельца магазина)', required=False)

    def handle(self, *args, **options):
        file_path = options['file']
        user_id = options['user']

        if not os.path.exists(file_path):
            self.stderr.write(f"Файл не найден: {file_path}")
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                self.stderr.write(f"Ошибка парсинга YAML: {e}")
                return

        # Начинаем транзакцию
        with transaction.atomic():
            try:
                self.load_data(data, user_id)
                self.stdout.write(self.style.SUCCESS('Данные успешно загружены'))
            except Exception as e:
                self.stderr.write(f"Ошибка при загрузке: {e}")
                raise  # Чтобы транзакция откатилась

    def load_data(self, data, user_id):
        shop_name = data.get('shop')
        url = data.get('url')
        filename = data.get('filename')  # не используется, но можно сохранить в будущем

        # Получаем или создаём пользователя (если указан)
        user = None
        if user_id:
            user = User.objects.filter(id=user_id, type='shop').first()
            if not user:
                self.stderr.write(f"Пользователь с ID={user_id} и типом 'shop' не найден")
                # Можно создать? Или продолжим без владельца

        # Создаём/обновляем магазин
        shop, created = Shop.objects.update_or_create(
            name=shop_name,
            defaults={'url': url, 'user': user}
        )
        self.stdout.write(f"{'Создан' if created else 'Обновлён'} магазин: {shop.name}")

        # Категории
        category_mapping = {}  # id из YAML → объект Category
        for cat_data in data.get('categories', []):
            category_id = cat_data['id']
            category_name = cat_data['name']

            category, _ = Category.objects.get_or_create(
                id=category_id,
                defaults={'name': category_name}
            )
            # Связываем с магазином
            shop.categories.add(category)
            category_mapping[category_id] = category
            self.stdout.write(f" Категория: {category.name}")

        # Товары
        for good_data in data.get('goods', []):
            category_id = good_data['category']
            category = category_mapping.get(category_id)
            if not category:
                self.stderr.write(f"Категория с ID={category_id} не найдена")
                continue

            # Продукт
            product, _ = Product.objects.get_or_create(
                name=good_data['name'],
                category=category
            )

            # ProductInfo
            product_info, _ = ProductInfo.objects.update_or_create(
                external_id=good_data['id'],
                shop=shop,
                product=product,
                defaults={
                    'model': good_data['model'],
                    'price': good_data['price'],
                    'price_rrc': good_data['price_rrc'],
                    'quantity': good_data['quantity'],
                }
            )

            # Параметры
            for param_name, param_value in good_data['parameters'].items():
                parameter, _ = Parameter.objects.get_or_create(name=param_name)
                ProductParameter.objects.update_or_create(
                    product_info=product_info,
                    parameter=parameter,
                    defaults={'value': str(param_value)}
                )

        self.stdout.write("Загрузка завершена!")