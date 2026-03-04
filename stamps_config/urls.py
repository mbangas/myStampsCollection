"""URLs principais do projeto myStampsCollection."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/catalogo/', permanent=False)),
    path('contas/', include('accounts.urls', namespace='accounts')),
    path('catalogo/', include('catalog.urls', namespace='catalog')),
    path('colecao/', include('collection.urls', namespace='collection')),
    path('trocas/', include('exchange.urls', namespace='exchange')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
