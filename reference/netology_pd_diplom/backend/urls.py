from django.urls import path
from django_rest_passwordreset.views import reset_password_request_token, reset_password_confirm

from backend.views import (
    PartnerUpdate, RegisterAccount, LoginAccount, CategoryView, ShopView,
    ProductInfoView, BasketView, AccountDetails, ContactView, OrderView,
    PartnerState, PartnerOrders, ConfirmAccount, ProductExportView,
    AsyncProductExportView, DownloadExportFileView, AsyncImportView,
    AsyncUpdatePriceListView, PublicStatsView, UserAvatarUploadView,
    ProductMainImageUploadView, ProductGalleryImageView
)

from backend.social_auth_views import (
    SocialAuthRedirectView, SocialAuthCallbackView, SocialAuthExchangeTokenView
)

app_name = 'backend'
urlpatterns = [
    # Партнеры
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),
    path('partner/state', PartnerState.as_view(), name='partner-state'),
    path('partner/orders', PartnerOrders.as_view(), name='partner-orders'),

    # Пользователи
    path('user/register', RegisterAccount.as_view(), name='user-register'),
    path('user/register/confirm', ConfirmAccount.as_view(), name='user-register-confirm'),
    path('user/details', AccountDetails.as_view(), name='user-details'),
    path('user/contact', ContactView.as_view(), name='user-contact'),
    path('user/login', LoginAccount.as_view(), name='user-login'),
    path('user/password_reset', reset_password_request_token, name='password-reset'),
    path('user/password_reset/confirm', reset_password_confirm, name='password-reset-confirm'),

    # Каталог
    path('categories', CategoryView.as_view(), name='categories'),
    path('shops', ShopView.as_view(), name='shops'),
    path('products', ProductInfoView.as_view(), name='products'),
    path('basket', BasketView.as_view(), name='basket'),
    path('order', OrderView.as_view(), name='order'),

    # Экспорт товаров (синхронный) - общие пути должны быть в конце
    path('products/export/async/', AsyncProductExportView.as_view(), name='product-export-async'),
    path('products/export/download/<str:filename>/', DownloadExportFileView.as_view(), name='product-export-download'),
    path('products/export/<str:format>/', ProductExportView.as_view(), name='product-export-format'),
    path('products/export/', ProductExportView.as_view(), name='product-export'),

    # Асинхронные операции
    path('import/async/', AsyncImportView.as_view(), name='async-import'),
    path('partner/update/async/', AsyncUpdatePriceListView.as_view(), name='async-partner-update'),

    # Статистика
    path('stats/', PublicStatsView.as_view(), name='public-stats'),

    # Для соцсетей
    path('auth/redirect/<str:provider>/', SocialAuthRedirectView.as_view(), name='social-auth-redirect'),
    path('auth/callback/<str:backend>/', SocialAuthCallbackView.as_view(), name='social-auth-callback'),
    path('auth/exchange/<str:provider>/', SocialAuthExchangeTokenView.as_view(), name='social-auth-exchange'),

    # Загрузка изображений
    path('user/avatar/', UserAvatarUploadView.as_view(), name='user-avatar'),
    path('product/<int:product_id>/main-image/', ProductMainImageUploadView.as_view(), name='product-main-image'),
    path('product/<int:product_id>/gallery/', ProductGalleryImageView.as_view(), name='product-gallery'),
]