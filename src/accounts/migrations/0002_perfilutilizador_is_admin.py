# Generated migration – adds is_admin field to PerfilUtilizador

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilutilizador',
            name='is_admin',
            field=models.BooleanField(
                default=False,
                help_text='O primeiro utilizador registado é automaticamente o administrador.',
                verbose_name='Administrador',
            ),
        ),
    ]
