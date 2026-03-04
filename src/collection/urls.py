"""URLs da aplicação Coleção."""

from django.urls import path

from . import views

app_name = 'collection'

urlpatterns = [
    path('', views.vista_colecao, name='colecao'),
    path('adicionar/<int:selo_id>/', views.adicionar_selo, name='adicionar_selo'),
    path('editar/<int:pk>/', views.editar_item, name='editar_item'),
    path('remover/<int:pk>/', views.remover_item, name='remover_item'),
]
