import time
import requests
from statistics import mean, median


def test_api_performance(url, iterations=10):
    """Тестирование производительности API"""

    times = []

    for i in range(iterations):
        start = time.time()
        response = requests.get(url)
        elapsed = time.time() - start

        times.append(elapsed)
        print(f"Запрос {i+1}: {elapsed:.3f} сек")

        # Проверяем заголовки кэша
        if 'X-Cache-Hit' in response.headers:
            print(f"  Кэш: {response.headers['X-Cache-Hit']}")

    print(f"\nСтатистика для {url}:")
    print(f"  Среднее: {mean(times):.3f} сек")
    print(f"  Медиана: {median(times):.3f} сек")
    print(f"  Мин: {min(times):.3f} сек")
    print(f"  Макс: {max(times):.3f} сек")


if __name__ == '__main__':
    # Тест без кэша (первый запуск)
    print("ПЕРВЫЙ ЗАПРОС (холодный кэш):")
    test_api_performance('http://localhost:8000/api/v1/categories', iterations=1)

    print("\nПОСЛЕДУЮЩИЕ ЗАПРОСЫ (горячий кэш):")
    test_api_performance('http://localhost:8000/api/v1/categories', iterations=5)