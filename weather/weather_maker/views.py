from django.http import HttpResponseRedirect
from django.shortcuts import render
from weather_maker.models import *
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView
from weather_maker.forms import *
import datetime
from weather_maker.weather_maker_api import WeatherFromAPIMaker, ApiError


# Create your views here.

class IndexView(TemplateView):
    template_name = 'weather_maker/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['get_current_weather_form'] = GetCurrentWeatherForm()
        return context

    def post(self, request):
        get_current_weather_form = GetCurrentWeatherForm(request.POST)

        if get_current_weather_form.is_valid():
            weather_maker_obj = WeatherFromAPIMaker(**get_current_weather_form.cleaned_data)
            try:
                weather_maker_obj.execute()
                current_weather_data_list = weather_maker_obj.current_weather_obj.fields_to_display
                return render(request, 'weather_maker/index.html', context={'current_weather_data_list': current_weather_data_list,
                                                                            'get_current_weather_form': get_current_weather_form})
            except ApiError as exc:
                return render(request, 'weather_maker/index.html',
                              context={'get_current_weather_form': get_current_weather_form,
                                       'error_message': exc.args[0]})



