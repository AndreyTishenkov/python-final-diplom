from django.core.cache import cache
from django.db.models import Q
from backend.models import ProductInfo
import hashlib
import json


def get_cached_products(shop_id=None, category_id=None, min_price=None, max_price=None, in_stock=None):
    """
    Кэширование результатов фильтрации товаров

    Параметры:
    - shop_id: ID магазина
    - category_id: ID категории
    - min_price: минимальная цена
    - max_price: максимальная цена
    - in_stock: только товары в наличии (True/False)
    """

    # Создаём уникальный ключ на основе всех параметров фильтрации
    filters_dict = {
        'shop_id': shop_id,
        'category_id': category_id,
        'min_price': min_price,
        'max_price': max_price,
        'in_stock': in_stock
    }

    # Убираем None значения
    filters_dict = {k: v for k, v in filters_dict.items() if v is not None}

    # Создаём хеш ключа для кэша
    cache_key = hashlib.md5(
        json.dumps(filters_dict, sort_keys=True).encode()
    ).hexdigest()

    cache_key = f'products_filter_{cache_key}'

    # Пытаемся получить из кэша
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        print(f"[CACHE HIT] {cache_key}")
        return cached_result

    print(f"[CACHE MISS] {cache_key}")

    # Строим запрос к БД
    queryset = ProductInfo.objects.filter(shop__state=True)

    # Фильтр по магазину
    if shop_id:
        queryset = queryset.filter(shop_id=shop_id)

    # Фильтр по категории
    if category_id:
        queryset = queryset.filter(product__category_id=category_id)

    # Фильтр по минимальной цене
    if min_price:
        queryset = queryset.filter(price__gte=min_price)

    # Фильтр по максимальной цене
    if max_price:
        queryset = queryset.filter(price__lte=max_price)

    # Фильтр по наличию
    if in_stock and in_stock.lower() == 'true':
        queryset = queryset.filter(quantity__gt=0)

    # Оптимизируем запрос (подгружаем связанные данные)
    queryset = queryset.select_related(
        'shop',
        'product__category'
    ).prefetch_related(
        'product_parameters__parameter'
    )

    # Сохраняем результат в кэш на 15 минут
    cache.set(cache_key, queryset, timeout=60*15)

    return queryset


def invalidate_products_cache():
    """Очистка всех кэшированных списков товаров"""
    cache.delete_pattern('products_filter_*')
    cache.delete_pattern('*.views.decorators.cache.cache_page.*')
    print("[CACHE] Products cache invalidated")