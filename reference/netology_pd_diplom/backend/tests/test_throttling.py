from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from backend.models import User


class ThrottlingTestCase(TestCase):
    """
    Тесты для проверки ограничения частоты запросов (throttling)
    """

    def setUp(self):
        """Подготовка перед каждым тестом"""
        cache.clear()
        self.client = APIClient()

        self.user = User.objects.create_user(
            email='throttle_test@example.com',
            password='testpass123',
            first_name='Throttle',
            last_name='Test',
            type='buyer',
            is_active=True
        )

    def test_register_throttle(self):
        """
        Тест ограничения на регистрацию: не более 5 регистраций в час.
        """
        url = reverse('backend:user-register')
        cache.clear()

        # Делаем 5 запросов (должны пройти)
        for i in range(5):
            response = self.client.post(url, {
                'first_name': f'User{i}',
                'last_name': 'Test',
                'email': f'test{i}@example.com',
                'password': 'Test123!',
                'company': '',
                'position': ''
            })
            self.assertNotEqual(
                response.status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
                f'Запрос {i+1} не должен был быть ограничен'
            )

        # 6-й запрос должен быть ограничен
        response = self.client.post(url, {
            'first_name': 'User6',
            'last_name': 'Test',
            'email': 'test6@example.com',
            'password': 'Test123!',
            'company': '',
            'position': ''
        })
        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            '6-й запрос регистрации должен быть ограничен'
        )

    def test_login_throttle(self):
        """
        Тест ограничения на авторизацию.
        """
        cache.clear()

        url = reverse('backend:user-login')
        wrong_data = {'email': 'throttle_test@example.com', 'password': 'wrong_password'}

        throttled_count = 0
        failed_auth_count = 0

        for i in range(15):
            response = self.client.post(url, wrong_data)

            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled_count += 1
            elif response.status_code == status.HTTP_200_OK:
                response_data = response.json()
                if response_data.get('Status') is False:
                    failed_auth_count += 1
                else:
                    self.fail(f'Запрос {i+1} не должен был авторизоваться')

        self.assertGreater(failed_auth_count, 0, 'Должны быть неудачные попытки')
        self.assertGreater(throttled_count, 0, 'После 15 запросов должно быть ограничение')

    def test_authenticated_user_throttle(self):
        """Тест для авторизованных пользователей"""
        cache.clear()
        self.client.force_authenticate(user=self.user)

        url = reverse('backend:basket')

        throttled_at = None
        for i in range(250):
            response = self.client.get(url)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled_at = i + 1
                break

        if throttled_at:
            self.assertGreater(
                throttled_at, 50,
                f'Ограничение наступило слишком рано на запросе {throttled_at}'
            )

    def test_export_throttle(self):
        """Тест ограничения на экспорт"""
        cache.clear()
        self.client.force_authenticate(user=self.user)

        url = reverse('backend:product-export')

        throttled_at = None
        for i in range(25):
            response = self.client.get(url)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled_at = i + 1
                break

        if throttled_at:
            self.assertGreaterEqual(
                throttled_at, 20,
                f'Ограничение экспорта наступило на запросе {throttled_at}'
            )

    def test_throttle_headers(self):
        """Тест заголовков при ограничении"""
        cache.clear()

        url = reverse('backend:user-login')
        wrong_data = {'email': 'throttle_test@example.com', 'password': 'wrong_password'}

        for i in range(15):
            response = self.client.post(url, wrong_data)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                self.assertIn('Retry-After', response.headers)
                self.assertTrue(response.headers['Retry-After'].isdigit())
                break

    def test_different_ips_different_limits(self):
        """Тест разных IP"""
        cache.clear()

        url = reverse('backend:user-register')

        # Первый IP
        for i in range(5):
            response = self.client.post(url, {
                'first_name': f'IP1_{i}',
                'last_name': 'Test',
                'email': f'ip1_{i}@example.com',
                'password': 'Test123!',
                'company': '',
                'position': ''
            })
            self.assertNotEqual(
                response.status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
                f'IP1 запрос {i+1} не должен быть ограничен'
            )

        # Меняем IP
        self.client.defaults['HTTP_X_FORWARDED_FOR'] = '192.168.1.100'

        # Второй IP
        for i in range(5):
            response = self.client.post(url, {
                'first_name': f'IP2_{i}',
                'last_name': 'Test',
                'email': f'ip2_{i}@example.com',
                'password': 'Test123!',
                'company': '',
                'position': ''
            })
            self.assertNotEqual(
                response.status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
                f'IP2 запрос {i+1} не должен быть ограничен'
            )

        del self.client.defaults['HTTP_X_FORWARDED_FOR']