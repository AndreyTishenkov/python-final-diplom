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
cd reference/netology_pd_diplom

2. Создание и активация виртуального окружения
python3 -m venv venv
source venv/bin/activate

3. Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt

4. Настройка переменных окружения
Создайте файл .env в корне проекта "netology_pd_diplom":

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
python manage.py load_yaml export_files/shop1.yaml --user=1

Создание тестовых заказов для админки
python manage.py create_test_orders

8. Запуск сервера
python manage.py runserver

Откройте в браузере:

Главная страница: http://localhost:8000/

Админ-панель: http://localhost:8000/admin/

API: http://localhost:8000/api/v1/

Запуск Celery (для асинхронных задач)
Установка и запуск Redis в соседем терменале
sudo apt update
sudo apt install redis-server -y   # Linux
sudo systemctl start redis-server
Проверка того, что redis запущен
redis-cli ping   --  ответ PONG

Запуск Celery worker
cd reference/netology_pd_diplom
source venv/bin/activate
celery -A netology_pd_diplom worker -l info

Запуск Celery beat (планировщик периодических задач) в третьем терминале
cd reference/netology_pd_diplom
source venv/bin/activate
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

Сначала входим в интерактивную строку Django
python manage.py shell

Затем вставляем код ниже, тем самым создав нового пользователя
from backend.models import User
user = User.objects.get(email='ivan@example.com')
print(f"Email: {user.email}")
print(f"is_active: {user.is_active}")
print(f"type: {user.type}")
print(f"Пароль установлен: {user.has_usable_password()}")

# Принудительно установим флаг активного пользователя
if not user.is_active:
    user.is_active = True
    user.save()
    print("Пользователь активирован")

# Ещё раз установим пароль
user.set_password('Test123!')
user.save()
print("Пароль установлен заново")

Выходим из Django shell
exit()

Вводим
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
  -H "Authorization: Token ваш_токен_который_вы_получили_в_пункте_2" \
  -H "Content-Type: application/json" \
  -d '{"format": "json"}'

--+++  Проверка статуса
curl "http://localhost:8000/api/v1/products/export/async/?task_id=TASK_ID_котрый_вы_только_что_получили"

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
  "total_orders": 6,
  "total_users": 4,
  "total_products": 19,
  "active_shops": 2
}

2) Админ-дашборд
Доступен по адресу: http://localhost:8000/admin/dashboard/

Отображает:
Количество заказов по статусам
Финансовую статистику
Активных пользователей и магазины
Товары с низким остатком

--+++  Тестирование
Создание тестовых данных, если ранее этого не сделали
python manage.py create_test_orders

Проверка API:
1) Проверка категорий
curl http://localhost:8000/api/v1/categories

2) Проверка магазинов
curl http://localhost:8000/api/v1/shops

3) Проверка товаров
curl http://localhost:8000/api/v1/products

Запуск тестов
python manage.py shell -c "from backend.tests.test_orders_demo import run; run()"

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
   


# Доработка дипломного проекта согласно замечаниям преподавателя

Исправления в дипломном проекте:
1.	Я внёс необходимые модули в requiremets.txt, к сожалению, этот был другой файл, во внешней директории. Заменил файл на правильный.

2.	Удалил не используемый файл в backend/tests.py

3.	Внёс изменения в файлы backend/signals.py, tasks.py и views.py admin_utils/order_notifications.p для постановки задач в очередь через “delay”. 
Для проверки асинхронной работы с celery необходимо запустить тестовый файл через путь: python backend/tests/test_celery.py

4.	В проект добавлена работа с DRF-Specular. Реализована работа Swagger UI, которая доступна по адресу /api/schema/swagger-ui/. 
Документация генерируется автоматически из кода, строк документации и сериализаторов.

5.	Настроил проект под throttling. Внёс ограничивающие данные для количества запросов в settings.py, создал файл для работы throttling, 
добавил файл тестирования на ограничение запросов в файле backend/tests/test_throttling.py.

6.	Настроена авторизация для соцсетей:
a.	После установки social-auth-app-django были сделаны миграции через команду «python manage.py migrate social_django»
b.	Добавил в настройки параметры авторизации на google и github
c.	Обновил файлы urls.py
d.	Создал файл для работы с авторизацией в соцсетях social_auth_views.py
e.	Проверка авторизации прошла успешно через команду curl "http://localhost:8000/api/v1/auth/redirect/github/" и curl "http://localhost:8000/api/v1/auth/redirect/google-oauth2/"

7.	Настроена возможность установки, просмотра и удаления аватара и его размера:
a.	Создан файл backend/image_processing.py для обработки изображений, совместимый с celery
b.	Обновлена административная панель, в которой отображаются аватары пользователей, а также их статус и права.
c.	Добавление аватара происходит через административную панель, либо при помощи кода:
curl -X POST http://localhost:8000/api/v1/user/avatar/ \
  -H "Authorization: Token ваш_токен" \
  -F "avatar=@/path/to/avatar.jpg"
  
8.	Установил зависимости с отправками ошибок на сайт sentry.io
a.	Установил sentry-sdk
b.	В файле settings.py были добавлены настройки для sentry
c.	Создан файл middleware.py для sentry, который отвечает за отправку сообщения в sentry.io с отображением у кого произошла ошибка, в каком месте ломается и какой запрос при этом был введён.
d.	Добавлены классы в backend/views.py для работы с sentry
e.	Обновлены пути для sentry

9.	Проделал работа с кешированием запросов к базе данных
a.	Установил модули django-redis, hiredis, django-cacheops
b.	Настроил отдельную бузу данных для redis (1), для celery использует 0.
c.	Настроена cacheops для автоматического кэширования запросов к конкретным моделям с разными временами продолжительности работы
d.	Для /api/v1/products был применён декоратор @cache_page, который кэширует полный HTTP-ответ на 30 минут. Это означает, 
что при повторных запросах с одинаковыми параметрами сервер не выполняет повторную выборку из БД, а мгновенно возвращает сохранённый ответ.
e.	В файле signals.py были добавлены обработчики, которые автоматически очищают кэш при изменении данных
f.	Для проверки работы кеширования можно использовать команду curl http://localhost:8000/api/v1/products?shop_id=1 несколько раз подряд.
g.	Создан файл tests/test_performance.py для проверки работы кеширования, который можно запустить командой python backend/tests/test_performance.py

10.	Использование инструмента silk для анализа кода на быстроту ответа на запросы к базе данных:
a.	Установил модуль silk
b.	Добавлены настройки в файл settings.py для silk
c.	Обновлены пути для silk
d.	Выполнены миграции с silk
e.	Проведена оптимизация кода в файле views.py: в метод export_csv были добавлены select_related - для подгрузки связанных товаров, 
категорий и магазинов и prefetch_related - для подгрузки параметров товаров. Это позволило загружать все связанные данные одним запросом 
вместо множества, которые были до оптимизации.


