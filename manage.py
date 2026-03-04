#!/usr/bin/env python
"""Utilitário de linha de comandos do Django para tarefas administrativas."""
import os
import sys


def main():
    """Executa tarefas administrativas."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stamps_config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. Confirme que está instalado e "
            "disponível no ambiente virtual e que DJANGO_SETTINGS_MODULE está definido."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
