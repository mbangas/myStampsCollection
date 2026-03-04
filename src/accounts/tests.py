"""Testes da aplicação Contas."""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import PerfilUtilizador


class SinalPerfilUtilizadorTests(TestCase):
    """Testes dos sinais post_save que gerem o PerfilUtilizador."""

    def test_criar_utilizador_cria_perfil_automaticamente(self):
        """Ao criar um utilizador, deve ser criado um PerfilUtilizador."""
        utilizador = User.objects.create_user(
            username='teste_sinal', password='Pass1234!'
        )
        self.assertTrue(
            PerfilUtilizador.objects.filter(utilizador=utilizador).exists()
        )

    def test_perfil_associado_ao_utilizador_correto(self):
        """O perfil criado automaticamente deve pertencer ao utilizador certo."""
        utilizador = User.objects.create_user(
            username='teste_assoc', password='Pass1234!'
        )
        self.assertEqual(utilizador.perfil.utilizador, utilizador)

    def test_guardar_utilizador_sem_perfil_cria_perfil(self):
        """Guardar um utilizador sem perfil deve criar um via get_or_create."""
        utilizador = User.objects.create_user(
            username='sem_perfil', password='Pass1234!'
        )
        # Eliminar o perfil criado pelo sinal criar_perfil_utilizador
        PerfilUtilizador.objects.filter(utilizador=utilizador).delete()
        self.assertFalse(PerfilUtilizador.objects.filter(utilizador=utilizador).exists())

        # Guardar o utilizador deve recriar o perfil via get_or_create
        utilizador.save()
        self.assertTrue(PerfilUtilizador.objects.filter(utilizador=utilizador).exists())

    def test_guardar_utilizador_com_perfil_nao_duplica(self):
        """Guardar um utilizador com perfil existente não deve criar duplicados."""
        utilizador = User.objects.create_user(
            username='com_perfil', password='Pass1234!'
        )
        self.assertEqual(
            PerfilUtilizador.objects.filter(utilizador=utilizador).count(), 1
        )
        utilizador.save()
        self.assertEqual(
            PerfilUtilizador.objects.filter(utilizador=utilizador).count(), 1
        )


class PerfilUtilizadorModelTests(TestCase):
    """Testes do modelo PerfilUtilizador."""

    def setUp(self):
        self.utilizador = User.objects.create_user(
            username='modelo_teste', password='Pass1234!'
        )
        self.perfil = self.utilizador.perfil

    def test_str_devolve_nome_correto(self):
        """__str__ deve devolver 'Perfil de <username>'."""
        self.assertEqual(str(self.perfil), f'Perfil de {self.utilizador.username}')

    def test_total_selos_sem_colecao(self):
        """total_selos deve devolver 0 quando não há itens na coleção."""
        self.assertEqual(self.perfil.total_selos, 0)

    def test_total_repetidos_sem_colecao(self):
        """total_repetidos deve devolver 0 quando não há itens na coleção."""
        self.assertEqual(self.perfil.total_repetidos, 0)


class FormularioRegistoTests(TestCase):
    """Testes do formulário de registo."""

    def _dados_validos(self, **kwargs):
        dados = {
            'username': 'novo_user',
            'first_name': 'Novo',
            'last_name': 'User',
            'email': 'novo@teste.pt',
            'password1': 'ComplexPass99!',
            'password2': 'ComplexPass99!',
        }
        dados.update(kwargs)
        return dados

    def test_formulario_valido(self):
        """Formulário com dados corretos deve ser válido."""
        from .forms import FormularioRegisto
        form = FormularioRegisto(data=self._dados_validos())
        self.assertTrue(form.is_valid(), form.errors)

    def test_email_duplicado_invalida_formulario(self):
        """Email já em uso deve invalidar o formulário."""
        from .forms import FormularioRegisto
        User.objects.create_user(username='existente', email='dup@teste.pt', password='x')
        form = FormularioRegisto(data=self._dados_validos(email='dup@teste.pt'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_passwords_diferentes_invalida_formulario(self):
        """Palavras-passe diferentes devem invalidar o formulário."""
        from .forms import FormularioRegisto
        form = FormularioRegisto(data=self._dados_validos(password2='Diferente99!'))
        self.assertFalse(form.is_valid())


class VistaRegistoTests(TestCase):
    """Testes da vista de registo."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:registar')

    def test_get_devolve_200(self):
        """GET na vista de registo deve devolver 200."""
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'accounts/registo.html')

    def test_registo_cria_utilizador_e_perfil(self):
        """POST válido deve criar utilizador, perfil e redirecionar."""
        dados = {
            'username': 'registo_user',
            'first_name': 'Registo',
            'last_name': 'User',
            'email': 'registo@teste.pt',
            'password1': 'ComplexPass99!',
            'password2': 'ComplexPass99!',
        }
        resposta = self.client.post(self.url, dados)
        self.assertRedirects(resposta, reverse('catalog:catalogo'))
        utilizador = User.objects.get(username='registo_user')
        self.assertTrue(PerfilUtilizador.objects.filter(utilizador=utilizador).exists())

    def test_utilizador_autenticado_redireciona(self):
        """Utilizador já autenticado deve ser redirecionado para o catálogo."""
        User.objects.create_user(username='ja_existe', password='Pass1234!')
        self.client.login(username='ja_existe', password='Pass1234!')
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, reverse('catalog:catalogo'))

    def test_post_invalido_nao_cria_utilizador(self):
        """POST com dados inválidos não deve criar utilizador."""
        resposta = self.client.post(self.url, {'username': '', 'password1': 'a'})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(username='').exists())


class VistaEntradaTests(TestCase):
    """Testes da vista de login."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:entrar')
        self.utilizador = User.objects.create_user(
            username='login_user', password='Pass1234!'
        )

    def test_get_devolve_200(self):
        """GET na vista de login deve devolver 200."""
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'accounts/entrar.html')

    def test_login_correto_redireciona(self):
        """Credenciais corretas devem autenticar e redirecionar."""
        resposta = self.client.post(self.url, {
            'username': 'login_user',
            'password': 'Pass1234!',
        })
        self.assertRedirects(resposta, reverse('catalog:catalogo'))

    def test_login_errado_volta_ao_formulario(self):
        """Credenciais erradas não devem autenticar."""
        resposta = self.client.post(self.url, {
            'username': 'login_user',
            'password': 'errada',
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.wsgi_request.user.is_authenticated)

    def test_utilizador_autenticado_redireciona(self):
        """Utilizador já autenticado deve ser redirecionado para o catálogo."""
        self.client.login(username='login_user', password='Pass1234!')
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, reverse('catalog:catalogo'))


class VistaSairTests(TestCase):
    """Testes da vista de logout."""

    def setUp(self):
        self.client = Client()
        self.utilizador = User.objects.create_user(
            username='sair_user', password='Pass1234!'
        )

    def test_sair_termina_sessao(self):
        """Logout deve terminar a sessão e redirecionar para login."""
        self.client.login(username='sair_user', password='Pass1234!')
        resposta = self.client.get(reverse('accounts:sair'))
        self.assertRedirects(resposta, reverse('accounts:entrar'))
        resposta_perfil = self.client.get(reverse('accounts:perfil'))
        self.assertEqual(resposta_perfil.status_code, 302)  # redireciona para login

    def test_sair_sem_login_redireciona(self):
        """Aceder ao logout sem estar autenticado deve redirecionar."""
        resposta = self.client.get(reverse('accounts:sair'))
        self.assertIn(resposta.status_code, [302, 200])


class VistaPerfilTests(TestCase):
    """Testes da vista de perfil."""

    def setUp(self):
        self.client = Client()
        self.utilizador = User.objects.create_user(
            username='perfil_user',
            email='perfil@teste.pt',
            password='Pass1234!',
        )
        self.url = reverse('accounts:perfil')

    def test_perfil_requer_autenticacao(self):
        """Vista de perfil deve redirecionar utilizadores não autenticados."""
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/contas/entrar/', resposta['Location'])

    def test_get_perfil_devolve_200(self):
        """GET no perfil autenticado deve devolver 200."""
        self.client.login(username='perfil_user', password='Pass1234!')
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'accounts/perfil.html')

    def test_get_perfil_sem_perfil_cria_perfil(self):
        """GET no perfil deve funcionar mesmo que o PerfilUtilizador não exista."""
        self.client.login(username='perfil_user', password='Pass1234!')
        PerfilUtilizador.objects.filter(utilizador=self.utilizador).delete()
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(PerfilUtilizador.objects.filter(utilizador=self.utilizador).exists())
