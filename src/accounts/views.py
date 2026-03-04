"""Vistas da aplicação Contas."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.generic import CreateView
from django.urls import reverse_lazy

from .forms import FormularioRegisto, FormularioEntrada, FormularioPerfil
from .models import PerfilUtilizador


class VistaRegisto(CreateView):
    """Vista de registo de novo utilizador."""

    form_class = FormularioRegisto
    template_name = 'accounts/registo.html'
    success_url = reverse_lazy('catalog:catalogo')

    def form_valid(self, form):
        utilizador = form.save()
        login(self.request, utilizador)
        messages.success(self.request, f'Bem-vindo(a), {utilizador.first_name or utilizador.username}!')
        return redirect(self.success_url)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('catalog:catalogo')
        return super().dispatch(request, *args, **kwargs)


class VistaEntrada(LoginView):
    """Vista de autenticação."""

    form_class = FormularioEntrada
    template_name = 'accounts/entrar.html'

    def form_valid(self, form):
        messages.success(self.request, f'Bem-vindo(a) de volta, {form.get_user().username}!')
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('catalog:catalogo')
        return super().dispatch(request, *args, **kwargs)


@login_required
def vista_sair(request):
    """Termina a sessão do utilizador."""
    logout(request)
    messages.info(request, 'Sessão terminada com sucesso.')
    return redirect('accounts:entrar')


@login_required
def vista_perfil(request):
    """Mostra e edita o perfil do utilizador autenticado."""
    perfil, _ = PerfilUtilizador.objects.get_or_create(utilizador=request.user)

    if request.method == 'POST':
        formulario = FormularioPerfil(request.POST, request.FILES, instance=perfil)
        if formulario.is_valid():
            # Actualiza campos do utilizador
            utilizador = request.user
            utilizador.first_name = formulario.cleaned_data['first_name']
            utilizador.last_name = formulario.cleaned_data['last_name']
            utilizador.email = formulario.cleaned_data['email']
            utilizador.save()
            formulario.save()
            messages.success(request, 'Perfil atualizado com sucesso.')
            return redirect('accounts:perfil')
    else:
        formulario = FormularioPerfil(instance=perfil)

    context = {
        'formulario': formulario,
        'perfil': perfil,
    }
    return render(request, 'accounts/perfil.html', context)
