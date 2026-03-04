"""URLs da aplicação Trocas."""

from django.urls import path

from . import views

app_name = 'exchange'

urlpatterns = [
    path('', views.vista_trocas, name='trocas'),
    path('matches/', views.vista_matches, name='matches'),
    path('propor/<int:utilizador_id>/', views.propor_troca, name='propor_troca'),
    path('responder/<int:troca_id>/', views.responder_troca, name='responder_troca'),
    path('concluir/<int:troca_id>/', views.concluir_troca, name='concluir_troca'),
]
