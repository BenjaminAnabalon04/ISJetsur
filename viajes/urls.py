from django.urls import path
from . import views

app_name = 'viajes'

urlpatterns = [
    path('', views.lista, name='lista'),
]
