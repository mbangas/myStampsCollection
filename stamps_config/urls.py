"""URLs principais do projeto myStampsCollection."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from home.views import landing_page


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_page, name='landing_page'),
    path('contas/', include('accounts.urls', namespace='accounts')),
    path('catalogo/', include('catalog.urls', namespace='catalog')),
    path('colecao/', include('collection.urls', namespace='collection')),
    path('trocas/', include('exchange.urls', namespace='exchange')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
