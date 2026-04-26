import sentry_sdk, time
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


class SentryUserContextMiddleware(MiddlewareMixin):
    """
    Добавляет информацию о пользователе в контекст Sentry
    """

    def process_request(self, request):
        if request.user and request.user.is_authenticated:
            sentry_sdk.set_user({
                'id': request.user.id,
                'email': request.user.email,
                'username': request.user.username,
                'type': request.user.type,
            })

        # Добавляем информацию о запросе
        sentry_sdk.set_tag('url', request.path)
        sentry_sdk.set_tag('method', request.method)


class CacheMonitorMiddleware:
    """Для мониторинга эффективности кэша"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Запоминаем время начала
        start_time = time.time()

        # Проверяем, был ли уже кэширован этот ответ
        cache_key = f'response_{request.path}_{request.method}'
        cached_response = cache.get(cache_key)

        if cached_response:
            # Если есть в кэше - возвращаем
            return cached_response

        # Если нет - обрабатываем запрос
        response = self.get_response(request)

        # Кэшируем GET запросы (кроме авторизованных)
        if request.method == 'GET' and not request.user.is_authenticated:
            cache.set(cache_key, response, timeout=300)

        # Добавляем заголовки для отладки
        response['X-Cache-Time'] = str(round(time.time() - start_time, 3))
        response['X-Cache-Hit'] = 'true' if cached_response else 'false'

        return response