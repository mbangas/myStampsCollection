"""URLs da aplicação Contas."""

from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('registar/', views.VistaRegisto.as_view(), name='registar'),
    path('entrar/', views.VistaEntrada.as_view(), name='entrar'),
    path('sair/', views.vista_sair, name='sair'),
    path('perfil/', views.vista_perfil, name='perfil'),
]
