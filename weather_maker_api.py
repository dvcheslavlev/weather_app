# -*- coding: utf-8 -*
# TODO API прогноза погоды https://www.weatherapi.com . 1млн запросов в месяц бесплатно, думаю для наших целей хватит
#  В бесплатной подписке максимальный прогноз на 3 дня (текущая дата + 2).
#  СУБД -  SQLite.
import datetime
import requests
import calendar
import cv2
import os
import bs4
import textwrap
from playhouse.db_url import connect
from peewee import DoesNotExist
from weather_db_init import database_proxy, LocationWeatherData, Location

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
        self.fields_to_image = [self.city, self.date, self.weekday, self.temp_str, self.condition]

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
        self.fields_to_image = [self.city, self.date, self.time, self.weekday, self.temp_str, self.condition, self.wind]

    def __str__(self):
        return f"City: {self.city}\nDate: {self.date}\n{self.time}\n{self.weekday}\n{self.temp_str}\n" \
               f"Condition: {self.condition}\n" \
               f"Wind: {self.wind}\n"


class WeatherMaker:

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

        self.current_weather_obj = CurrentWeather(city=self.city,
                                                  date=datetime_data.date(),
                                                  time=datetime_data.time(),
                                                  temp='Temperature: ' + str(weather_data['current']['temp_c']),
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


class ImageMaker:

    def __init__(self, template_file_path):
        self.template = cv2.imread(template_file_path)

    def __get_icon_img(self, weather_obj, cur_ind=''):
        '''
        Метод принимает объект DayWeather или CurrentWeather, получает из него url иконки (ее предоставляет АПИ),
        скачивает файл и сохраняет в папку temp
        :param weather_obj: DayWeather or CurrentWeather instance
        :param cur_ind: str to add into a filename of CurrentWeather instance icon
        :return: None
        '''
        icon = requests.get(weather_obj.icon_url)
        os.makedirs('temp', exist_ok=True)
        # TODO makerdirs  а не mkdir именно из-за параметра exist_ok. Чтобы не падала FileExistsError: [Errno 17] File exists: 'temp'
        file_name = f'temp/{cur_ind}{weather_obj.date.strftime("%Y-%m-%d")}_icon.jpg'
        with open(file_name, 'wb') as ff:
            ff.write(icon.content)
        weather_obj.icon_file_path = file_name

    def __temp_files_delete(self):
        # Метод удаляет временные файлы иконок из папки temp
        *_, filenames = next(os.walk('temp'))
        for file in filenames:
            file_path = os.path.join('temp', file)
            os.remove(file_path)

    def draw_gradient(self, condition):
        template_h, template_w = self.template.shape[:2]

        def gr_c(template, b, g, r, offset, b_change=False, g_change=False, r_change=False):
            x = 0
            b = b
            g = g
            r = r
            while x < template_w:
                for x in range(x, x + offset):
                    for y in range(0, template_h):
                        template[y, x] = [b, g, r]
                x += 1
                if b_change:
                    b = b + 1 if b < 235 else 235
                if g_change:
                    g = g + 1 if g < 235 else 235
                if r_change:
                    r = r + 1 if r < 235 else 235
            return template

        if condition == 'sun':
            gr_c(template=self.template, b=0, g=255, r=255, offset=template_w // 255, b_change=True)
        elif condition == 'rain':
            gr_c(template=self.template, b=255, g=0, r=0, offset=template_w // 255, g_change=True, r_change=True)
        elif condition == 'snow':
            gr_c(template=self.template, b=255, g=170, r=66, offset=template_w // 220, b_change=True,
                 g_change=True, r_change=True)
        elif condition == 'cloud':
            gr_c(template=self.template, b=128, g=128, r=128, offset=template_w // 128, b_change=True,
                 g_change=True, r_change=True)

    # TODO  я решил все же воспользоваться OpenCV. Это оказалось весьма нетривиально, т.ч. я каждый шаг алгоритма описал
    def __text_insert(self, position_y, position_x, text_lines_list, font_scale):
        '''
        Метод принимает список строк, которые будут написаны на карточке, координаты первой строки и масштаб шрифта
        :param position_y: int
        :param position_x: int
        :param text_lines_list: list
        :return:
        '''
        position_y = position_y
        for line in text_lines_list:
            cv2.putText(self.template, text=str(line), org=(position_x, position_y), fontFace=cv2.FONT_HERSHEY_COMPLEX,
                        fontScale=font_scale,
                        color=(0, 0, 0), thickness=1, lineType=cv2.LINE_AA)
            position_y += 20

    def __icon_insert(self, icon_path, position_y, position_x):
        '''
        Это оказалась самая жесть. Вставка иконки. Метод принимает путь до файла иконки и координаты
        :param icon_path: str or path
        :param position_y: int
        :param position_x: int
        :return:
        '''
        # открываем иконку
        icon_img = cv2.imread(icon_path, -1)
        # забираем ее высоту и ширину
        icon_h, icon_w = icon_img.shape[:2]
        # выставляем Region of interest на подложке - то место куда встанет иконка
        template_roi = self.template[position_y:position_y + icon_h, position_x:position_x + icon_w]
        # создаем маску и инвертированную маску иконки
        mask = icon_img[:, :, 3]
        mask_inverted = cv2.bitwise_not(mask)
        # приводим иконку к 3хканальному виду (без альфа канала, если он там есть - а он там может быть. или не быть=)))
        # Подложка точно 3х канальная
        icon_img = icon_img[:, :, 0:3]
        # "вырезаем" в подложке место под иконку с помощью инвертированной маски
        template_bg = cv2.bitwise_and(template_roi, template_roi, mask=mask_inverted)
        # вырезаем саму иконку из файла иконки с помощье ее маски
        icon_fg = cv2.bitwise_and(icon_img, icon_img, mask=mask)
        #  dst - это ROI  со вставленной иконкой
        dst = cv2.add(template_bg, icon_fg)
        # вставляем dst  в подложку
        self.template[position_y:position_y + icon_h, position_x:position_x + icon_w] = dst

    def img_execute_single(self, weather_obj, x, y, condition=''):
        '''
        Метод отрисовывает карточку с погодой 1 дня. Принимает объект DayWeather или  CurrentWeather и координаты текста.
        После отрисовки карточка демонстрируется, а временный файл иконки удаляется
        :param condition:  str
        :param weather_obj: объект DayWeather или  CurrentWeather
        :param x: int
        :param y: int
        :return:
        '''
        self.__get_icon_img(weather_obj, cur_ind='cur_')
        if condition:
            self.draw_gradient(condition=condition)
        self.__text_insert(position_x=x, position_y=y,
                           text_lines_list=weather_obj.fields_to_image,
                           font_scale=0.6)
        self.__icon_insert(icon_path=weather_obj.icon_file_path, position_y=y - 25, position_x=x + 130)
        # демонстрация файла открытки
        viewImage(self.template)
        # очистка папки temp от иконок
        self.__temp_files_delete()


class DatabaseUpdater:

    def __init__(self, db_url):
        '''
        Коннект с БД и создание таблиц на ините объекта.
        Создаются 2 таблицы
        Location - города, по которымв БД есть данные о погоде
        LocationWeatherData - собственно данные о погоде за каждый день
        :param db_url: str
        '''
        self.db_url = db_url
        db = connect(self.db_url)
        database_proxy.initialize(db)
        db.create_tables([Location, LocationWeatherData])

    def db_write(self, weather_maker_obj):
        '''
        Метод принимает объект WeatherMaker и обращается к его полю forecast_weather_obj_list - списку прогнозов по городу
        за 3 дня (включая текущий). Сначала заполняется таблица Location  (с проверкой дубля) затем LocationWeatherData
        :param weather_maker_obj: WeatherMaker instance
        :return:
        '''
        if Location.get_or_none(Location.location == weather_maker_obj.city.lower()) is None:
            location = Location(location=weather_maker_obj.city.lower())
            location.save()
        else:
            location = Location.get(Location.location == weather_maker_obj.city.lower())

        for day_forecast in weather_maker_obj.forecast_weather_obj_list:
            # пишем в таблицу прогнозов, а если прогноз на этот город-дату УЖЕ есть - апдейтим
            if LocationWeatherData.get_or_none(LocationWeatherData.city == weather_maker_obj.city.lower(),
                                               LocationWeatherData.date == day_forecast.date) is None:
                LocationWeatherData.create(location=location,
                                           city=weather_maker_obj.city.lower(),
                                           date=day_forecast.date,
                                           weekday=day_forecast.weekday,
                                           t_min=day_forecast.temp_min,
                                           t_max=day_forecast.temp_max,
                                           condition=day_forecast.condition,
                                           icon_url=day_forecast.icon_url)
            else:
                update = LocationWeatherData.update({LocationWeatherData.t_min: day_forecast.temp_min,
                                                     LocationWeatherData.t_max: day_forecast.temp_max,
                                                     LocationWeatherData.condition: day_forecast.condition,
                                                     LocationWeatherData.icon_url: day_forecast.icon_url}).where(
                    LocationWeatherData.city == weather_maker_obj.city,
                    LocationWeatherData.date == day_forecast.date)
                update.execute()

    def db_get_day_weather(self, city, date):
        '''
        Метод принимает город, дату и возвращает один объект DayWeather, созданный по данным из БД за дату
        Если данные не найдены (город отсутствует в таблице  Location или данные по погоде за дату отсутствуют в таблице
        LocationWeatherData) рейзятся исключения (пробрасываются дальше в других методах).
        :param city: str
        :param date: datetime instance
        :return: DayWeather instance
        '''
        try:
            city = Location.get(Location.location == city.lower())
            try:
                data = LocationWeatherData.get(LocationWeatherData.location_id == city,
                                               LocationWeatherData.date == date)
                return DayWeather(city=data.city.title(),
                                  date=data.date,
                                  temp=f'{data.t_min} - {data.t_max}',
                                  temp_min=data.t_min,
                                  temp_max=data.t_max,
                                  condition=data.condition,
                                  icon_url=data.icon_url,
                                  )
            except DoesNotExist:
                raise NoDateDataError()
        except DoesNotExist:
            raise NoCityError(f'DB does not content weather data for this city, please try another...\n')

    def db_get_period_weather(self, city, start_date, end_date):
        '''
        Метод принимает стартовую дату, конечную дату и город. Возвращает 2 списка - 1. список подходящих по дате объектов
        DayWeather и 2. список объектов datetime - дат, по которым в БД отсутствует информация
        :param city: str
        :param start_date: datetime instance
        :param end_date: datetime instance
        :return: tuple of lists
        '''
        period_results_list = []
        period_fail_list = []
        date = start_date
        while start_date <= date <= end_date:
            try:
                day_result = self.db_get_day_weather(city=city, date=date)
                period_results_list.append(day_result)
                date += datetime.timedelta(days=1)
            except NoCityError as exc:
                raise exc
            except NoDateDataError:
                period_fail_list.append(date)
                date += datetime.timedelta(days=1)
        return period_results_list, period_fail_list


class WeatherInterface:

    def __init__(self, db_url, template_file_path):
        self.db_updater = DatabaseUpdater(db_url=db_url)
        self.template_file_path = template_file_path

    def __connect_api(self, city):
        #  соединение с апи, создание объекта  WeatherMaker
        weather_maker_obj = WeatherMaker(city=city)
        weather_maker_obj.execute()
        return weather_maker_obj

    def __handle_user_card_choice(self, weather_obj):
        # обработка пользовательского выбора картинки
        gui_choice = input('Create card? y/n ---->')
        if gui_choice == 'y':
            img = ImageMaker(template_file_path=self.template_file_path)
            if 'солн' in weather_obj.condition.lower():
                img.img_execute_single(weather_obj=weather_obj, x=100, y=100, condition='sun')
            elif 'дожд' in weather_obj.condition.lower():
                img.img_execute_single(weather_obj=weather_obj, x=100, y=100, condition='rain')
            elif 'снег' in weather_obj.condition.lower():
                img.img_execute_single(weather_obj=weather_obj, x=100, y=100, condition='snow')
            elif 'обла' in weather_obj.condition.lower() or 'пасмур' in weather_obj.condition.lower():
                img.img_execute_single(weather_obj=weather_obj, x=100, y=100, condition='cloud')
            else:
                img.img_execute_single(weather_obj=weather_obj, x=100, y=100)

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

    def update_all_db(self):
        # работает аналогично методу update_db_one_city, но принимает не пользовательский ввод, а поочередно
        # обновляет (добавляет) строки по ВСЕМ городам, которые есть в БД.
        print('Updating data for all cities in DB from API.\n')
        data = Location.select()
        for city in data:
            self.db_updater.db_write(self.__connect_api(city.location))
        print(f'\nAll cities data in DB was updated.')

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

    def get_API_terms(self):
        html = requests.get('https://www.weatherapi.com/terms.aspx', verify=False).text
        soup = bs4.BeautifulSoup(html, 'html.parser')
        terms_block = soup.find('div', attrs={'id': "feature-2"})
        exile = terms_block.find('span').find_parent()
        exile.decompose()

        text_lead = terms_block.find('p', attrs={'class': "lead"})
        text_tag = terms_block.find_all('p')
        header_tag = terms_block.find_all('h3')

        print(f'{textwrap.fill(text_lead.text, 100)}\n')

        for text, header in zip(text_tag[1:], header_tag):
            if not text.find('span'):
                wrapped_text = textwrap.fill(text.text, 100)
                print(f'{header.text}\n{wrapped_text}\n')


def viewImage(image, name_of_window='Default'):
    cv2.namedWindow(name_of_window, cv2.WINDOW_NORMAL)
    cv2.imshow(name_of_window, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()






