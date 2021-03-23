# -*- coding: utf-8 -*

import datetime
import requests
import calendar
import os
import textwrap

API_KEY = 'dfdd96671c1349f190983225200212'
# язык, на котором вернется "Облачно", "Дождь" и тд.
LANG = 'ru'


class NoCityError(Exception):
    pass


class NoDateDataError(Exception):
    pass


class ApiError(Exception):
    pass


class DayWeather:
    '''
    В этот объект заворачиваются данные по погоде за 1 день. Мне показалось это более удобным чем словарь (как в задании)
    '''

    def __init__(self, city, date, temp, condition, icon_url, temp_min, temp_max):
        self.city = city
        self.date = date
        self.weekday = calendar.day_name[calendar.weekday(date.year, date.month, date.day)]
        self.temp_str = temp
        # temp_str - это строковое представление "от ... до". temp_min и temp_max это float, напр. для последующего
        # поиска в БД, сортировки и тд.
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.condition = condition
        self.icon_url = icon_url
        self.icon_file_path = ''
        self.fields_to_display = [self.city, self.date, self.weekday, self.temp_str, self.condition]

    def __str__(self):
        return f"City: {self.city}\nDate: {self.date}\n{self.weekday}\nTemperature: {self.temp_str}\n" \
               f"Condition: {self.condition}\n"


class CurrentWeather(DayWeather):
    '''
    Немного расширенный DayWeather (текущее время, ветер)
    '''

    def __init__(self, city, date, time, temp, wind, condition, icon_url):
        super().__init__(city, date, temp, condition, icon_url, temp_min=None, temp_max=None)
        self.time = time
        self.wind = wind
        self.fields_to_display = [f'City: {self.city}',
                                  f'Date: {self.date}',
                                  f'Time: {self.time}',
                                  f'Weekday: {self.weekday}',
                                  f'Temperature: {self.temp_str}',
                                  f'Condition: {self.condition}',
                                  f'Wind: {self.wind}']

    def __str__(self):
        return f"City: {self.city}\nDate: {self.date}\n{self.time}\n{self.weekday}\n{self.temp_str}\n" \
               f"Condition: {self.condition}\n" \
               f"Wind: {self.wind}\n"


class WeatherFromAPIMaker:

    def __init__(self, city, days=3):
        '''
        Принимает город и кол-во дней прогноза (макс. 3).
        Объект  WeatherMaker содержит в себе данные по текущей погоде в городе и прогнозе на 3 дня.
        :param city: city name, str.
        :param days: int, number of forecast days (1 - 3), default = 3. If None set only current weather will shown.
        '''
        self.city = None
        self.current_weather_obj = None
        self.forecast_weather_obj_list = []
        self.params = {'key': API_KEY, 'q': city, 'lang': LANG, 'days': days, 'is_day': 1}

    def __get_weather_data(self):
        # подключение к апи и получение респонса
        response = requests.get(url='http://api.weatherapi.com/v1/forecast.json', params=self.params)
        data = response.json()
        if 'error' not in data:
            return data
        else:
            return data['error']['message']

    def __collect_current_weather_data(self, weather_data):
        # создание объекта CurrentWeather
        datetime_data = datetime.datetime.strptime(weather_data['location']['localtime'], '%Y-%m-%d %H:%M')
        self.city = f"{weather_data['location']['name']}"
        wind_count = f'Wind: {round((weather_data["current"]["wind_kph"] * 1000 / 3600), 0)} ' \
                     f'mps, {weather_data["current"]["wind_dir"]}'
        print(str(weather_data['current']['temp_c']))

        self.current_weather_obj = CurrentWeather(city=self.city,
                                                  date=datetime_data.date(),
                                                  time=datetime_data.time(),
                                                  temp=str(weather_data['current']['temp_c']),
                                                  wind=wind_count,
                                                  condition=weather_data['current']['condition']['text'],
                                                  icon_url='http:' + weather_data['current']['condition']['icon'],
                                                  )

    def __collect_forecast_weather_data(self, weather_data):
        # создание "прогноза" - список объектов DayWeather на 3 дня (включая текущий) в поле forecast_weather_obj_list
        for forecast in weather_data['forecast']['forecastday']:
            date_data = datetime.datetime.strptime(forecast['date'], '%Y-%m-%d')
            day_weather_obj = DayWeather(city=self.city,
                                         date=date_data.date(),
                                         temp=f" {forecast['day']['mintemp_c']} - {forecast['day']['maxtemp_c']}",
                                         temp_min=forecast['day']['mintemp_c'],
                                         temp_max=forecast['day']['maxtemp_c'],
                                         condition=forecast['day']['condition']['text'],
                                         icon_url='http:' + forecast['day']['condition']['icon'],
                                         )
            self.forecast_weather_obj_list.append(day_weather_obj)

    def execute(self):
        raw_weather_data = self.__get_weather_data()
        if isinstance(raw_weather_data, str):
            # если в респонсе ошибка (напр., несуществующий город) рейзится исключение
            raise ApiError(raw_weather_data)
        else:
            self.__collect_current_weather_data(raw_weather_data)
            self.__collect_forecast_weather_data(raw_weather_data)


class WeatherInterface:

    def __init__(self, db_url, template_file_path):
        self.template_file_path = template_file_path

    def __connect_api(self, city):
        #  соединение с апи, создание объекта  WeatherMaker
        weather_maker_obj = WeatherFromAPIMaker(city=city)
        weather_maker_obj.execute()
        return weather_maker_obj

    def update_db_one_city(self):
        # обновление БД погодой (прогноз 3 дня) для 1 города из АПИ.

        # Напр., в БД есть данные по городу Moscow за 7 - 9 декабря. 9.12 вызывается метод на город Moscow.
        # В БД будут записаны строки за 10, 11 декабря, а строка за 9 декабря - обновлена (без новой записи!)

        # Или  9.12 вызывается метод по городу Ankara, которого нет в БД. В БД будут записаны данные по Ankara
        # за 9-11 декабря (3 строки)
        print('Updating one city data from API. If city data is not in DB, new city data will be created.\n')
        city = input('Enter city in English to update DB--->')
        try:
            self.db_updater.db_write(self.__connect_api(city))
            print(f'\nDB updated with city {city} data.')
        except ApiError as exc:
            print(f'Api error - {exc.args[0]}')

    # def update_all_db(self):
    #     # работает аналогично методу update_db_one_city, но принимает не пользовательский ввод, а поочередно
    #     # обновляет (добавляет) строки по ВСЕМ городам, которые есть в БД.
    #     print('Updating data for all cities in DB from API.\n')
    #     data = Location.select()
    #     for city in data:
    #         self.db_updater.db_write(self.__connect_api(city.location))
    #     print(f'\nAll cities data in DB was updated.')

    def get_weather_from_db_fp(self):
        # получение данных по погоде за период. Ввод принимает дату старта, дату окончания и город поиска.
        # в консоль выводятся данные по каждому дню периода и список дат, по которым данных нет. Если город
        # отсутствует в БД или по запрошенному периоду нет ни одной строки - выводятся соответствующие сообщения
        print('Getting weather data for period from DB.\n')
        while True:
            try:
                start = datetime.datetime.strptime(input('Enter start date DD-MM-YYYY ---->'), '%d-%m-%Y').date()
                end = datetime.datetime.strptime(input('Enter end date DD-MM-YYYY ---->'), '%d-%m-%Y').date()
                break
            except ValueError:
                print('Invalid date input! Enter date in format DD-MM-YYYY.')
        city = input('Enter city in English --->')
        try:
            result, fail = self.db_updater.db_get_period_weather(city=city, start_date=start, end_date=end)
            if result:
                for day_data in result:
                    print(f'\n{day_data}')
                if fail:
                    print(f'\nDB does not content weather data for these dates:')
                    for date in fail:
                        print(date)
            elif not result:
                print(f'\nDB does not content weather data for any of entered dates.\n')
        except NoCityError as exc:
            print(exc.args[0])

    def get_weather_from_db_f_day(self):
        # получение данных по погоде в ОДНОМ городе за ОДНУ дату. Ввод принимает дату и город поиска.
        # Обработка отсутствия города\данных на дату - ананлогично методу get_weather_from_db_fp
        # По желанию пользователя формируется и выводится картинка.
        print('Getting weather data for one day from DB.\n')
        while True:
            try:
                date = datetime.datetime.strptime(input('Enter date DD-MM-YYYY ---->'), '%d-%m-%Y').date()
                break
            except ValueError:
                print('Invalid date input! Enter date in format DD-MM-YYYY.')
        city = input('Enter city in English--->')
        try:
            result = self.db_updater.db_get_day_weather(city=city, date=date)
            print(f'\n{result}')
            self.__handle_user_card_choice(weather_obj=result)

        except NoCityError as exc:
            print(exc.args[0])
        except NoDateDataError:
            print('DB does not content weather data for this date.\n')

    def get_current_weather_from_api(self):
        # получение данных по текущей погоде в ОДНОМ городе из АПИ. Ввод принимает город поиска.
        # По желанию пользователя формируется и выводится картинка.
        print('Getting current weather data from API.\n')
        city = input('Enter city in English to get current weather --->')
        try:
            weather_obj = self.__connect_api(city).current_weather_obj
            print(f'\n{weather_obj}')
            self.__handle_user_card_choice(weather_obj=weather_obj)
        except ApiError as exc:
            print(f'Api error - {exc.args[0]}')

    def get_forecast_from_api(self):
        # получение прогноза на 3 дня в ОДНОМ городе из АПИ. Ввод принимает город поиска.
        print('Getting 3 days weather forecast from API.\n')
        city = input('Enter city in English to get weather forecast --->')
        try:
            for day_forecast in self.__connect_api(city).forecast_weather_obj_list:
                print(f'\n{day_forecast}')
        except ApiError as exc:
            print(f'Api error - {exc.args[0]}')
