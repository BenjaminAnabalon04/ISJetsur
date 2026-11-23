from django.urls import path

from . import views

app_name = 'usuarios'

urlpatterns = [
    path('', views.usuarios, name='usuarios'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/nuevo/', views.crear_usuario, name='crear_usuario'),
    path(
        'usuarios/<int:id_usuario>/desbloquear/',
        views.desbloquear_usuario,
        name='desbloquear_usuario',
    ),
    path('logout/', views.logout_view, name='logout'),
]
