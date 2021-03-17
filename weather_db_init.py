# -*- coding: utf-8 -*-
import peewee

database_proxy = peewee.DatabaseProxy()


class BaseTable(peewee.Model):
    class Meta:
        database = database_proxy


class Location(BaseTable):
    location = peewee.CharField()


class LocationWeatherData(BaseTable):
    location = peewee.ForeignKeyField(Location)
    city = peewee.CharField()
    date = peewee.DateField()
    weekday = peewee.CharField()
    t_min = peewee.FloatField()
    t_max = peewee.FloatField()
    condition = peewee.CharField()
    icon_url = peewee.CharField()
