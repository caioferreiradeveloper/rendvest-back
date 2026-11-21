from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .bolsai import MarketDataUnavailable, get_market_data
from .models import MarketSnapshot

REFRESH_INTERVAL = timedelta(hours=1)


@transaction.atomic
def get_market_snapshot(endpoint, format_response):
    snapshot, _ = MarketSnapshot.objects.select_for_update().get_or_create(endpoint=endpoint)
    if snapshot.fetched_at and timezone.now() - snapshot.fetched_at < REFRESH_INTERVAL:
        return snapshot.data

    try:
        data = format_response(get_market_data(endpoint, quote=True))
    except (MarketDataUnavailable, NotFound):
        if snapshot.fetched_at is not None:
            return snapshot.data
        raise

    snapshot.data = data
    snapshot.fetched_at = timezone.now()
    snapshot.save(update_fields=["data", "fetched_at"])
    return data
