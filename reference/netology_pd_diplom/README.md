# Пример API-сервиса для магазина

[Документация по запросам в PostMan](https://documenter.getpostman.com/view/5037826/SVfJUrSc) 




## **Получить исходный код**

    git config --global user.name "YOUR_USERNAME"
    
    git config --global user.email "your_email_address@example.com"
    
    mkdir ~/my_diplom
    
    cd my_diplom
    
    git clone git@github.com:A-Iskakov/netology_pd_diplom.git
    
    cd netology_pd_diplom
    
    sudo pip3 install  --upgrade pip
    
    sudo pip3 install -r requirements.txt
    
    python3 manage.py makemigrations
     
    python3 manage.py migrate
    
    python3 manage.py createsuperuser    
    
 
## **Проверить работу модулей**
    
    
    python3 manage.py runserver 0.0.0.0:8000


## **Установить СУБД (опционально)**

    sudo nano  /etc/apt/sources.list.d/pgdg.list
    
    ----->
    deb http://apt.postgresql.org/pub/repos/apt/ bionic-pgdg main
    <<----
    
    
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
    
    sudo apt-get update
    
    sudo apt-get install postgresql-11 postgresql-server-dev-11
    
    sudo -u postgres psql postgres
    
    create user diplom_user with password 'password';
    
    alter role diplom_user set client_encoding to 'utf8';
    
    alter role diplom_user set default_transaction_isolation to 'read committed';
    
    alter role diplom_user set timezone to 'Europe/Moscow';
    
    create database diplom_db owner mploy;
    alter user mploy createdb;



# Дипломный проект: Интернет-магазин с API и админ-панелью

## О проекте

Это полнофункциональный интернет-магазин с REST API, реализованный на Django REST Framework. Проект включает:

- Регистрацию и авторизацию пользователей (покупатели и магазины)
- Управление товарами, категориями и магазинами
- Корзину и систему заказов
- Экспорт/импорт товаров в форматах JSON, YAML, CSV
- Асинхронную обработку задач через Celery
- Email уведомления о статусе заказов
- Админ-панель с дашбордом и управлением заказами
- Публичную статистику для главной страницы

## Технологии

- **Backend:** Django 5.0, Django REST Framework
- **База данных:** SQLite (по умолчанию), поддерживается PostgreSQL
- **Асинхронные задачи:** Celery, Redis
- **Форматы данных:** JSON, YAML, CSV
- **Email:** SMTP (mail.ru)
- **Документация:** Postman коллекция

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```
1. Клонируем репозиторий:
git clone https://github.com/AndreyTishenkov/python-final-diplom.git
cd reference\netology_pd_diplom

2. Создание и активация виртуального окружения
python3 -m venv venv
source venv/bin/activate

3. Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt

4. Настройка переменных окружения
Создайте файл .env в корне проекта:

env
SECRET_KEY=your-secret-key-here
DEBUG=True
EMAIL_HOST_USER=your_email@mail.ru
EMAIL_HOST_PASSWORD=your_email_password

5. Применение миграций
python manage.py makemigrations
python manage.py migrate

6. Создание суперпользователя
python manage.py createsuperuser

7. Загрузка тестовых данных
Загрузка товаров из YAML файла
python manage.py load_yaml shop1.yaml --user=1

Создание тестовых заказов для админки
python manage.py create_test_orders

8. Запуск сервера
python manage.py runserver

Откройте в браузере:

Главная страница: http://localhost:8000/

Админ-панель: http://localhost:8000/admin/

API: http://localhost:8000/api/v1/

Запуск Celery (для асинхронных задач)
Установка и запуск Redis
sudo apt-get install redis-server  # Linux
brew install redis                 # Mac
redis-server

Docker:
docker run -d -p 6379:6379 --name redis redis

Запуск Celery worker
celery -A netology_pd_diplom worker -l info

Запуск Celery beat (планировщик периодических задач)
celery -A netology_pd_diplom beat -l info

API:
-------   Пользователи
Метод	                        URL	                        Описание
POST	               /api/v1/user/register	         Регистрация
POST	               /api/v1/user/register/confirm	 Подтверждение email
POST	               /api/v1/user/login	             Авторизация
GET/POST	           /api/v1/user/details	             Профиль пользователя
GET/POST/PUT/DELETE	   /api/v1/user/contact	             Контакты

-------   Каталог
Метод	      URL	                Описание
GET	    /api/v1/categories	    Список категорий
GET	    /api/v1/shops	        Список магазинов
GET	    /api/v1/products	    Товары с фильтрацией

-------   Корзина и заказы
Метод	                     URL	          Описание
GET/POST/PUT/DELETE	   /api/v1/basket	  Управление корзиной
GET/POST	           /api/v1/order	  Заказы

-------   Экспорт/Импорт
Метод	              URL	                             Описание
GET	    /api/v1/products/export/	                Синхронный экспорт
GET	    /api/v1/products/export/<format>/	        Экспорт (json/yaml/csv)
POST	/api/v1/products/export/async/	            Асинхронный экспорт
GET	    /api/v1/products/export/async/?task_id=	    Статус задачи
POST	/api/v1/import/async/	                    Асинхронный импорт

-------   Для магазинов
Метод	             URL	                      Описание
POST	    /api/v1/partner/update	        Обновление прайс-листа
GET/POST	/api/v1/partner/state	        Статус магазина
GET	        /api/v1/partner/orders	        Заказы магазина
POST	    /api/v1/partner/update/async/	Асинхронное обновление


======  Примеры запросов  ======
1) Регистрация пользователя
curl -X POST http://localhost:8000/api/v1/user/register \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Иван",
    "last_name": "Петров",
    "email": "ivan@example.com",
    "password": "Test123!",
    "company": "",
    "position": ""
  }'

2) Авторизация
curl -X POST http://localhost:8000/api/v1/user/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ivan@example.com", "password": "Test123!"}'

3) Получение списка товаров
curl "http://localhost:8000/api/v1/products?shop_id=1&category_id=1"

4) Экспорт товаров в JSON
curl "http://localhost:8000/api/v1/products/export/json/?shop_id=1" -o products.json

5) Асинхронный экспорт

--+++  Запуск экспорта
curl -X POST http://localhost:8000/api/v1/products/export/async/ \
  -H "Authorization: Token ваш_токен" \
  -H "Content-Type: application/json" \
  -d '{"format": "json"}'

--+++  Проверка статуса
curl "http://localhost:8000/api/v1/products/export/async/?task_id=ID_ЗАДАЧИ"

--+++  Управление заказами в админке
Функционал админки заказов:
Просмотр списка заказов - таблица со всеми заказами
Цветные статусы - визуальное отображение состояния

Кнопки действий:
Подтвердить заказ
Собрать заказ
Отправить заказ
Доставить заказ
Отменить заказ
Отправить уведомление
Фильтрация по статусу и дате
Поиск по ID, email, телефону
Массовые операции - подтверждение/отмена нескольких заказов
Автоматические email уведомления при смене статуса

Статусы заказов:
Статус	       Описание	          Доступные действия
new	          Новый заказ	    Подтвердить, Отменить
confirmed	  Подтвержден	    Собрать, Отменить
assembled	  Собран	        Отправить
sent	      Отправлен	        Доставить
delivered	  Доставлен	        Отправить уведомление
canceled	  Отменен	        ---

--+++  Статистика и дашборд
1) Публичная статистика
curl "http://localhost:8000/api/v1/stats/"
Ответ:
json
{
  "total_orders": 10,
  "total_users": 5,
  "total_products": 19,
  "active_shops": 1
}

2) Админ-дашборд
Доступен по адресу: http://localhost:8000/admin/dashboard/

Отображает:
Количество заказов по статусам
Финансовую статистику
Активных пользователей и магазины
Товары с низким остатком

--+++  Тестирование
Создание тестовых данных
python manage.py create_test_orders

Проверка API:
1) Проверка категорий
curl http://localhost:8000/api/v1/categories

2) Проверка магазинов
curl http://localhost:8000/api/v1/shops

3) Проверка товаров
curl http://localhost:8000/api/v1/products

Запуск тестов

python manage.py test backend.tests
Формат YAML файла для импорта товаров

yaml:
shop: "Название магазина"
url: "https://shop-url.ru"
categories:
  - id: 1
    name: "Смартфоны"
  - id: 2
    name: "Ноутбуки"
goods:
  - id: 1001
    category: 1
    name: "iPhone 15 Pro"
    model: "A2848"
    price: 99900
    price_rrc: 109900
    quantity: 50
    parameters:
      "Процессор": "A17 Pro"
      "Память": "256GB"
      "Цвет": "Черный"

Команды управления
                  Команда	                                            Описание
python manage.py runserver	                                       Запуск сервера
python manage.py createsuperuser	                               Создание администратора
python manage.py load_yaml <file> --user=<id>	                   Загрузка товаров из YAML
python manage.py create_test_orders	                               Создание тестовых заказов
python manage.py export_products --format json	                   Экспорт товаров в файл
celery -A netology_pd_diplom worker --pool=eventlet -l info	       Запуск Celery worker
celery -A netology_pd_diplom beat -l info	                       Запуск Celery beat

Настройка Email
Для отправки уведомлений используется SMTP (mail.ru по умолчанию):

python
EMAIL_HOST = 'smtp.mail.ru'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = 'your_email@mail.ru'
EMAIL_HOST_PASSWORD = 'your_password'

Возможные проблемы и их решения
Ошибка: ModuleNotFoundError: No module named 'celery'
pip install celery redis eventlet

Ошибка подключения к Redis
Убедитесь, что Redis запущен:
redis-cli ping
Должен ответить: PONG

Ошибка при импорте YAML
Убедитесь, что файл имеет правильную кодировку UTF-8:
python manage.py load_yaml export_files/shop1.yaml --user=1
   
