from django import forms


class GetCurrentWeatherForm(forms.Form):
    city = forms.CharField(max_length=30, label='Enter city:', widget=forms.TextInput(attrs={'id': 'city-name'}))

