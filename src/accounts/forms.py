"""Formulários da aplicação Contas."""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

from .models import PerfilUtilizador


class FormularioRegisto(UserCreationForm):
    """Formulário de registo de novo utilizador."""

    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'o-seu-email@exemplo.com'}),
    )
    first_name = forms.CharField(
        max_length=50,
        required=True,
        label='Nome',
        widget=forms.TextInput(attrs={'placeholder': 'O seu nome'}),
    )
    last_name = forms.CharField(
        max_length=50,
        required=False,
        label='Apelido',
        widget=forms.TextInput(attrs={'placeholder': 'O seu apelido'}),
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def clean_email(self) -> str:
        """Valida que o email não está já em uso."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este email já está a ser utilizado.')
        return email


class FormularioEntrada(AuthenticationForm):
    """Formulário de autenticação personalizado."""

    username = forms.CharField(
        label='Nome de Utilizador',
        widget=forms.TextInput(attrs={'placeholder': 'Nome de utilizador', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Palavra-passe',
        widget=forms.PasswordInput(attrs={'placeholder': 'Palavra-passe'}),
    )


class FormularioPerfil(forms.ModelForm):
    """Formulário de edição do perfil do utilizador."""

    first_name = forms.CharField(max_length=50, required=False, label='Nome')
    last_name = forms.CharField(max_length=50, required=False, label='Apelido')
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = PerfilUtilizador
        fields = ('bio', 'avatar', 'paises_interesse')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'paises_interesse': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs) -> None:
        """Pré-preenche os campos do utilizador a partir da instância do perfil."""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.utilizador_id:
            utilizador = self.instance.utilizador
            self.fields['first_name'].initial = utilizador.first_name
            self.fields['last_name'].initial = utilizador.last_name
            self.fields['email'].initial = utilizador.email
