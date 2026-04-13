from django.core.management.base import BaseCommand
from backend.tests.test_orders_demo import run


class Command(BaseCommand):
    help = 'Создает демонстрационные заказы для тестирования админки'

    def handle(self, *args, **options):
        run()