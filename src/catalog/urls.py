"""URLs da aplicação Catálogo."""

from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.VistaCatalogo.as_view(), name='catalogo'),
    path('pais/<int:pk>/', views.VistaPais.as_view(), name='pais_detalhe'),
    path('selo/<int:pk>/', views.VistaSeloDetalhe.as_view(), name='selo_detalhe'),
    path('selo/<int:pk>/upload-imagem/', views.vista_upload_imagem_selo, name='upload_imagem_selo'),
    path('criar-pais/', views.vista_criar_pais, name='criar_pais'),
]
