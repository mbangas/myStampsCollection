"""Modelos da aplicação Contas."""

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class PerfilUtilizador(models.Model):
    """Perfil alargado do utilizador com preferências da coleção."""

    utilizador = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Utilizador',
    )
    bio = models.TextField(
        blank=True,
        verbose_name='Biografia',
        help_text='Breve descrição sobre o colecionador.',
    )
    avatar = models.ImageField(
        upload_to='avatares/',
        blank=True,
        null=True,
        verbose_name='Foto de Perfil',
    )
    paises_interesse = models.ManyToManyField(
        'catalog.Pais',
        blank=True,
        related_name='utilizadores_interessados',
        verbose_name='Países de Interesse',
    )
    data_registo = models.DateTimeField(auto_now_add=True, verbose_name='Data de Registo')
    is_admin = models.BooleanField(
        default=False,
        verbose_name='Administrador',
        help_text='O primeiro utilizador registado é automaticamente o administrador.',
    )

    class Meta:
        verbose_name = 'Perfil do Utilizador'
        verbose_name_plural = 'Perfis dos Utilizadores'

    def __str__(self) -> str:
        return f'Perfil de {self.utilizador.username}'

    @property
    def total_selos(self) -> int:
        """Devolve o número total de selos na coleção do utilizador."""
        return self.utilizador.itens_colecao.aggregate(
            total=models.Sum('quantidade_possuida')
        )['total'] or 0

    @property
    def total_repetidos(self) -> int:
        """Devolve o número total de selos repetidos disponíveis para troca."""
        return self.utilizador.itens_colecao.aggregate(
            total=models.Sum('quantidade_repetidos')
        )['total'] or 0


@receiver(post_save, sender=User)
def criar_perfil_utilizador(sender: type, instance: User, created: bool, **kwargs) -> None:
    """Cria automaticamente um perfil ao registar um utilizador.

    O primeiro utilizador registado torna-se administrador automaticamente.
    """
    if created:
        is_admin = User.objects.count() == 1
        PerfilUtilizador.objects.create(utilizador=instance, is_admin=is_admin)


@receiver(post_save, sender=User)
def guardar_perfil_utilizador(sender: type, instance: User, created: bool, **kwargs) -> None:
    """Guarda o perfil quando o utilizador é guardado."""
    if not created:
        PerfilUtilizador.objects.get_or_create(utilizador=instance)
