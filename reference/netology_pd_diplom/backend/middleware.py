import sentry_sdk
from django.utils.deprecation import MiddlewareMixin


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