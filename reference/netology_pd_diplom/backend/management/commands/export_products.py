import os
import json
import csv
from django.core.management.base import BaseCommand
from django.utils import timezone
from backend.models import ProductInfo
import yaml


class Command(BaseCommand):
    help = 'Экспорт товаров в файл'

    def add_arguments(self, parser):
        parser.add_argument('--format', type=str, default='json',
                            choices=['json', 'yaml', 'csv'],
                            help='Формат экспорта')
        parser.add_argument('--output', type=str,
                            help='Путь к выходному файлу')
        parser.add_argument('--shop-id', type=int,
                            help='ID магазина для экспорта')
        parser.add_argument('--category-id', type=int,
                            help='ID категории для фильтрации')
        parser.add_argument('--min-price', type=int,
                            help='Минимальная цена')
        parser.add_argument('--max-price', type=int,
                            help='Максимальная цена')

    def handle(self, *args, **options):
        # Формируем queryset с фильтрами
        queryset = ProductInfo.objects.all()

        if options['shop_id']:
            queryset = queryset.filter(shop_id=options['shop_id'])

        if options['category_id']:
            queryset = queryset.filter(product__category_id=options['category_id'])

        if options['min_price']:
            queryset = queryset.filter(price__gte=options['min_price'])

        if options['max_price']:
            queryset = queryset.filter(price__lte=options['max_price'])

        # Подготавливаем данные
        data = []
        for product in queryset:
            item = {
                'id': product.id,
                'external_id': product.external_id,
                'name': product.product.name,
                'category': product.product.category.name,
                'model': product.model,
                'shop': product.shop.name,
                'quantity': product.quantity,
                'price': product.price,
                'price_rrc': product.price_rrc,
                'parameters': {p.parameter.name: p.value for p in product.product_parameters.all()}
            }
            data.append(item)

        # Определяем выходной файл
        output_file = options['output']
        if not output_file:
            output_file = f'export_products_{timezone.now().date()}.{options["format"]}'

        # Экспортируем
        if options['format'] == 'json':
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        elif options['format'] == 'yaml':
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        elif options['format'] == 'csv':
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                if data:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)

        self.stdout.write(self.style.SUCCESS(f'Экспорт завершен! Файл: {output_file}'))
        self.stdout.write(f'Экспортировано товаров: {len(data)}')