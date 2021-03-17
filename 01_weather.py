# -*- coding: utf-8 -*-

# В очередной спешке, проверив приложение с прогнозом погоды, вы выбежали
# навстречу ревью вашего кода, которое ожидало вас в офисе.
# И тут же день стал хуже - вместо обещанной облачности вас встретил ливень.

# Вы промокли, настроение было испорчено, и на ревью вы уже пришли не в духе.
# В итоге такого сокрушительного дня вы решили написать свою программу для прогноза погоды
# из источника, которому вы доверяете.

# Для этого вам нужно:

# Создать модуль-движок с классом WeatherMaker, необходимым для получения и формирования предсказаний.
# В нём должен быть метод, получающий прогноз с выбранного вами сайта (парсинг + re) за некоторый диапазон дат,
# а затем, получив данные, сформировать их в словарь {погода: Облачная, температура: 10, дата:datetime...}

# Добавить класс ImageMaker.
# Снабдить его методом рисования открытки
# (использовать OpenCV, в качестве заготовки брать lesson_016/python_snippets/external_data/probe.jpg):
#   С текстом, состоящим из полученных данных (пригодится cv2.putText)
#   С изображением, соответствующим типу погоды
# (хранятся в lesson_016/python_snippets/external_data/weather_img ,но можно нарисовать/добавить свои)
#   В качестве фона добавить градиент цвета, отражающего тип погоды
# Солнечно - от желтого к белому
# Дождь - от синего к белому
# Снег - от голубого к белому
# Облачно - от серого к белому

# Добавить класс DatabaseUpdater с методами:
#   Получающим данные из базы данных за указанный диапазон дат.
#   Сохраняющим прогнозы в базу данных (использовать peewee)

# Сделать программу с консольным интерфейсом, постаравшись все выполняемые действия вынести в отдельные функции.
# Среди действий, доступных пользователю, должны быть:
#   Добавление прогнозов за диапазон дат в базу данных
#   Получение прогнозов за диапазон дат из базы
#   Создание открыток из полученных прогнозов
#   Выведение полученных прогнозов на консоль
# При старте консольная утилита должна загружать прогнозы за прошедшую неделю.

# Рекомендации:
# Можно создать отдельный модуль для инициализирования базы данных.
# Как далее использовать эту базу данных в движке:
# Передавать DatabaseUpdater url-путь
# https://peewee.readthedocs.io/en/latest/peewee/playhouse.html#db-url
# Приконнектится по полученному url-пути к базе данных
# Инициализировать её через DatabaseProxy()
# https://peewee.readthedocs.io/en/latest/peewee/database.html#dynamically-defining-a-database
import sys

from weather_db_init import Location
from weather_maker_api import WeatherInterface

template_path = 'src/probe.jpg'
db_url = 'sqlite:///weather.db'


interface = WeatherInterface(db_url=db_url, template_file_path=template_path)

data = Location.select()
cities_list = []
for city in data:
    cities_list.append(str(city.location).title())
cities = ', '.join(cities_list)

print(
    f'Welcome to Weather Maker!\nOur DB includes weather data for cities:\n{cities}\n\n'
    f'Please, choose option from the list below:')

while True:
    options = [('Update data in DB for one city from API.', interface.update_db_one_city),
               ('Get weather from DB for period.', interface.get_weather_from_db_fp),
               ('Get weather from DB for one day.', interface.get_weather_from_db_f_day),
               ('Update data in DB for all cities from API', interface.update_all_db),
               ('Get current weather for city from API', interface.get_current_weather_from_api),
               ('Get 3 days forecast for city from API', interface.get_forecast_from_api),
               ("Read API's Terms of Service", interface.get_API_terms),
               ('Exit', sys.exit)]

    for numb, opt in enumerate(options, 1):
        print(f'{numb}. {opt[0]}')

    user_choice = input('---->>>')

    try:
        options[int(user_choice) - 1][1]()
    except (IndexError, ValueError):
        print('Invalid option choice! Please, choose option from the list below:')

# зачет!