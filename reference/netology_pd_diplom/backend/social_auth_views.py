from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from django.contrib.auth import login
from django.conf import settings
from social_core.backends.utils import load_backends
from social_django.utils import psa, load_strategy
from backend.models import User
import requests


class SocialAuthRedirectView(APIView):
    """
    Получение URL для редиректа на социальную сеть.

    Поддерживаемые провайдеры: google-oauth2, github

    Пример ответа:
    {
        "provider": "google-oauth2",
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
        "redirect_uri": "http://localhost:8000/auth/complete/google-oauth2/"
    }
    """
    permission_classes = [AllowAny]

    def get(self, request, provider):
        # Загружаем все доступные бекенды
        backends = load_backends(settings.AUTHENTICATION_BACKENDS)

        # Поддерживаемые имена провайдеров
        provider_mapping = {
            'google': 'google-oauth2',
            'google-oauth2': 'google-oauth2',
            'github': 'github',
        }

        # Преобразуем имя провайдера
        backend_name = provider_mapping.get(provider, provider)

        if backend_name not in backends:
            return Response({
                'error': f'Provider "{provider}" not supported',
                'supported_providers': list(backends.keys())
            }, status=400)

        backend = backends[backend_name]

        # Формируем URL для редиректа
        redirect_uri = request.build_absolute_uri(f'/auth/complete/{backend_name}/')

        # Получаем URL авторизации
        if hasattr(backend, 'auth_url'):
            auth_url = backend.auth_url()
        else:
            # Формируем вручную для Google
            if backend_name == 'google-oauth2':
                auth_url = (
                    f'https://accounts.google.com/o/oauth2/v2/auth?'
                    f'client_id={settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY}&'
                    f'redirect_uri={redirect_uri}&'
                    f'response_type=code&'
                    f'scope=email%20profile'
                )
            elif backend_name == 'github':
                auth_url = (
                    f'https://github.com/login/oauth/authorize?'
                    f'client_id={settings.SOCIAL_AUTH_GITHUB_KEY}&'
                    f'redirect_uri={redirect_uri}&'
                    f'scope=user:email'
                )
            else:
                auth_url = None

        return Response({
            'provider': backend_name,
            'authorization_url': auth_url,
            'redirect_uri': redirect_uri,
            'supported_providers': list(backends.keys())
        })


class SocialAuthCallbackView(APIView):
    """
    Обработка callback после авторизации в соц.сети.
    Возвращает токен DRF для дальнейшей работы с API.
    """
    permission_classes = [AllowAny]

    @psa('social:complete')
    def post(self, request, backend, *args, **kwargs):
        """
        Обмениваем код авторизации на токены и создаём/получаем пользователя.
        """
        try:
            # Получаем данные пользователя из соц.сети
            user = request.backend.do_auth(request.data.get('access_token'))

            if user and user.is_active:
                # Авторизуем пользователя в Django
                login(request, user)

                # Получаем или создаём DRF токен
                token, created = Token.objects.get_or_create(user=user)

                return Response({
                    'status': True,
                    'token': token.key,
                    'user_id': user.id,
                    'email': user.email,
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                })
            else:
                return Response({
                    'status': False,
                    'error': 'Authentication failed'
                }, status=401)

        except Exception as e:
            return Response({
                'status': False,
                'error': str(e)
            }, status=400)


class SocialAuthExchangeTokenView(APIView):
    """
    Обмен временного кода на access_token и получение DRF токена.
    Этот эндпоинт подходит для авторизации из фронтенда.
    """
    permission_classes = [AllowAny]

    def post(self, request, provider):
        """
        Обмениваем code на access_token и логиним пользователя.
        """
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri')

        if not code:
            return Response({'error': 'code is required'}, status=400)

        # Параметры для запроса к провайдеру
        token_urls = {
            'google-oauth2': 'https://oauth2.googleapis.com/token',
            'github': 'https://github.com/login/oauth/access_token',
        }

        client_configs = {
            'google-oauth2': {
                'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                'client_secret': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
                'code': code
            },
            'github': {
                'client_id': settings.SOCIAL_AUTH_GITHUB_KEY,
                'client_secret': settings.SOCIAL_AUTH_GITHUB_SECRET,
                'redirect_uri': redirect_uri,
                'code': code
            },
        }

        if provider not in token_urls:
            return Response({
                'error': f'Provider "{provider}" not supported',
                'supported': list(token_urls.keys())
            }, status=400)

        # Запрашиваем access_token
        try:
            response = requests.post(
                token_urls[provider],
                data=client_configs[provider],
                headers={'Accept': 'application/json'}
            )

            if response.status_code != 200:
                return Response({
                    'error': 'Failed to get access token',
                    'details': response.text
                }, status=400)

            token_data = response.json()
            access_token = token_data.get('access_token')

            if not access_token:
                return Response({
                    'error': 'access_token not received',
                    'details': token_data
                }, status=400)

            # Используем полученный access_token для аутентификации
            auth_response = self.authenticate_with_token(request, provider, access_token)
            return auth_response

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=400)

    def authenticate_with_token(self, request, provider, access_token):
        """
        Аутентификация пользователя с помощью access_token.
        """
        strategy = load_strategy(request)
        backends = load_backends(settings.AUTHENTICATION_BACKENDS)

        backend_cls = backends.get(provider)
        if not backend_cls:
            return Response({'error': f'Backend for {provider} not found'}, status=400)

        backend = backend_cls(strategy)

        try:
            # Получаем пользователя по access_token
            user = backend.do_auth(access_token)

            if user and user.is_active:
                login(request, user)
                token, _ = Token.objects.get_or_create(user=user)

                return Response({
                    'status': True,
                    'token': token.key,
                    'user_id': user.id,
                    'email': user.email,
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                })
            else:
                return Response({
                    'status': False,
                    'error': 'Authentication failed'
                }, status=401)

        except Exception as e:
            return Response({
                'status': False,
                'error': str(e)
            }, status=400)