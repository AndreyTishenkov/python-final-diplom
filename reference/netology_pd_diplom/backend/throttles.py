from rest_framework.throttling import SimpleRateThrottle


class RegisterThrottle(SimpleRateThrottle):
    """
    Ограничение на регистрацию новых пользователей.
    Не более X регистраций в час с одного IP.
    """
    scope = 'register'

    def get_cache_key(self, request, view):
        # Ограничиваем по IP адресу
        return self.get_ident(request)


class LoginThrottle(SimpleRateThrottle):
    """
    Ограничение на попытки авторизации.
    Не более X попыток в час с одного IP.
    """
    scope = 'login'

    def get_cache_key(self, request, view):
        # Ограничиваем по IP адресу + email (если указан)
        ident = self.get_ident(request)
        email = request.data.get('email', '')
        return f"{ident}_{email}" if email else ident


class ExportThrottle(SimpleRateThrottle):
    """
    Ограничение на экспорт товаров.
    Не более X экспортов в час.
    """
    scope = 'export'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return f"user_{request.user.id}"
        return self.get_ident(request)


class ImportThrottle(SimpleRateThrottle):
    """
    Ограничение на импорт товаров.
    Не более X импортов в час.
    """
    scope = 'import'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return f"user_{request.user.id}"
        return self.get_ident(request)


class BasketThrottle(SimpleRateThrottle):
    """
    Ограничение на операции с корзиной.
    Не более X операций в час.
    """
    scope = 'basket'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return f"user_{request.user.id}"
        return self.get_ident(request)


class OrderThrottle(SimpleRateThrottle):
    """
    Ограничение на создание заказов.
    Не более X заказов в час.
    """
    scope = 'order'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return f"user_{request.user.id}"
        return self.get_ident(request)