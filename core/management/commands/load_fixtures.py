from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Carrega dados de demonstração de usuários, ganhos e gastos."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Fixtures de demonstração só podem ser carregadas com DJANGO_DEBUG=True."
            )

        fixture_paths = [
            Path(settings.BASE_DIR) / "apps/users/fixtures/users.json",
            Path(settings.BASE_DIR) / "apps/transactions/fixtures/transactions.json",
            Path(settings.BASE_DIR) / "apps/loans/fixtures/loans.json",
        ]

        with transaction.atomic():
            call_command("loaddata", *(str(path) for path in fixture_paths), verbosity=0)

        self.stdout.write(self.style.SUCCESS("Fixtures de demonstração carregadas com sucesso."))
