from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework.exceptions import NotFound

from ...bolsai import MarketDataUnavailable
from ...fund_data import get_fund
from ...models import RealEstateFund
from ...snapshots import REFRESH_INTERVAL


class Command(BaseCommand):
    help = "Atualiza os FIIs cadastrados cuja última atualização tem pelo menos uma hora."

    def handle(self, *args, **options):
        tickers = list(
            RealEstateFund.objects.filter(updated_at__lte=timezone.now() - REFRESH_INTERVAL)
            .order_by("ticker")
            .values_list("ticker", flat=True)
        )
        failures = 0
        for ticker in tickers:
            try:
                get_fund(ticker, allow_stale=False)
            except (MarketDataUnavailable, NotFound):
                failures += 1
                self.stderr.write(f"{ticker}: atualização indisponível.")
        if failures:
            raise CommandError(f"{failures} de {len(tickers)} FIIs não foram atualizados.")
        self.stdout.write(f"{len(tickers)} FIIs verificados.")
