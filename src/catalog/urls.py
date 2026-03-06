"""URLs da aplicação Catálogo."""

from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.VistaCatalogo.as_view(), name='catalogo'),
    path('pais/<int:pk>/', views.VistaPais.as_view(), name='pais_detalhe'),
    path('pais/<int:pk>/editar-descricao/', views.vista_editar_descricao_pais, name='editar_descricao_pais'),
    path('pais/<int:pk>/apagar/', views.vista_confirmar_apagar_pais, name='apagar_pais'),
    path('selo/<int:pk>/', views.VistaSeloDetalhe.as_view(), name='selo_detalhe'),
    path('selo/<int:pk>/upload-imagem/', views.vista_upload_imagem_selo, name='upload_imagem_selo'),
    path('criar-pais/', views.vista_criar_pais, name='criar_pais'),
    path('importar-stampdata/', views.vista_iniciar_importacao_stampdata, name='importar_stampdata'),
    path('importar-stampdata/estado/', views.vista_estado_importacao, name='estado_importacao'),
    path('importar-stampdata/retomar/', views.vista_retomar_importacao, name='retomar_importacao'),
]
