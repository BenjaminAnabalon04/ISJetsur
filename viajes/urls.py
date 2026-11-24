from django.urls import path

from . import views

app_name = 'viajes'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('<int:id_viaje>/asientos/', views.asientos, name='asientos'),
    path('<int:id_viaje>/reservar/', views.reservar, name='reservar'),
    path('reservas/<int:id_reserva>/cobrar/', views.cobrar, name='cobrar'),
    path('tickets/', views.tickets, name='tickets'),
    path('tickets/<str:codigo>/', views.ticket, name='ticket'),
    path('reservas/<int:id_reserva>/cambiar/', views.cambiar, name='cambiar'),
    path('reservas/<int:id_reserva>/cancelar/', views.cancelar, name='cancelar'),
    path('nuevo/', views.viaje_nuevo, name='nuevo'),
    path('devoluciones/', views.devoluciones, name='devoluciones'),
    path('devoluciones/<str:codigo>/', views.devolver, name='devolver'),
]
