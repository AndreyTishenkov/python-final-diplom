import requests

# 1. Логин
print("=" * 50)
print("1. Авторизация")
print("=" * 50)

login_resp = requests.post(
    'http://localhost:8000/api/v1/user/login',
    json={'email': 'test_user@example.com', 'password': 'testpass123'}
)

print(f"Статус: {login_resp.status_code}")
print(f"Ответ: {login_resp.json()}")

token = login_resp.json().get('Token')

if token:
    print(f"\nТокен получен: {token[:20]}...")

    # 2. Асинхронный экспорт
    print("\n" + "=" * 50)
    print("2. Запуск асинхронного экспорта")
    print("=" * 50)

    export_resp = requests.post(
        'http://localhost:8000/api/v1/products/export/async/',
        headers={'Authorization': f'Token {token}'},
        json={'format': 'json', 'shop_id': 1}
    )

    print(f"Статус: {export_resp.status_code}")
    print(f"Ответ: {export_resp.json()}")

    task_id = export_resp.json().get('Task ID')

    if task_id:
        print(f"\nЗадача создана: {task_id}")

        # 3. Проверка статуса
        print("\n" + "=" * 50)
        print("3. Проверка статуса задачи")
        print("=" * 50)

        import time
        for i in range(5):
            time.sleep(2)
            status_resp = requests.get(
                f'http://localhost:8000/api/v1/products/export/async/?task_id={task_id}'
            )
            status = status_resp.json()
            print(f"Попытка {i+1}: Ready = {status.get('Ready')}")

            if status.get('Ready'):
                print(f"\nЗадача выполнена!")
                print(f"Результат: {status.get('Result')}")
                break
else:
    print("\nНе удалось получить токен. Проверьте логин.")