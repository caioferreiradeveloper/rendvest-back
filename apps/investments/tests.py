from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from .bolsai import MarketDataUnavailable
from .models import MarketSnapshot


class MarketSnapshotTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(SimpleNamespace(pk=1, is_authenticated=True))
        cache.clear()

    @patch("apps.investments.snapshots.get_market_data")
    def test_quotes_refresh_after_one_hour_and_keep_last_price_on_failure(self, fetch):
        for ticker in ("PETR4", "HGLG11"):
            with self.subTest(ticker=ticker):
                fetch.reset_mock()
                fetch.side_effect = None
                fetch.return_value = {"ticker": ticker, "close": 10, "trade_date": "2026-11-19"}
                url = f"/api/v1/investments/quotes/{ticker.lower()}/"
                self.assertEqual(self.client.get(url).json()["price"], "10.0000")

                snapshot = MarketSnapshot.objects.get(endpoint=f"stocks/{ticker}/quote")
                snapshot.fetched_at = timezone.now() - timedelta(minutes=59)
                snapshot.save(update_fields=["fetched_at"])
                self.assertEqual(self.client.get(url).json()["price"], "10.0000")
                fetch.assert_called_once()

                snapshot.fetched_at = timezone.now() - timedelta(hours=1)
                snapshot.save(update_fields=["fetched_at"])
                fetch.side_effect = MarketDataUnavailable()
                self.assertEqual(self.client.get(url).json()["price"], "10.0000")
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.data["price"], "10.0000")

                fetch.side_effect = None
                fetch.return_value["close"] = 12
                self.assertEqual(self.client.get(url).json()["price"], "12.0000")
                self.assertEqual(fetch.call_count, 3)

    @patch("apps.investments.snapshots.get_market_data")
    def test_fund_price_history_is_saved_separately_for_each_ticker(self, fetch):
        fetch.side_effect = [
            {"prices": [{"close": 100, "trade_date": "2026-11-19"}]},
            {"prices": [{"close": 110, "trade_date": "2026-11-19"}]},
            {"prices": [{"close": 120, "trade_date": "2026-11-19"}]},
        ]
        hglg = "/api/v1/investments/funds/HGLG11/prices/"
        kncr = "/api/v1/investments/funds/KNCR11/prices/"
        self.assertEqual(self.client.get(hglg).json()["prices"][0]["close"], 100)
        self.assertEqual(self.client.get(kncr).json()["prices"][0]["close"], 110)
        self.assertEqual(self.client.get(hglg).json()["prices"][0]["close"], 100)
        self.assertEqual(fetch.call_count, 2)

        MarketSnapshot.objects.filter(endpoint__startswith="stocks/HGLG11/").update(
            fetched_at=timezone.now() - timedelta(hours=1)
        )
        self.assertEqual(self.client.get(hglg).json()["prices"][0]["close"], 120)
        self.assertEqual(self.client.get(kncr).json()["prices"][0]["close"], 110)
        self.assertEqual(fetch.call_count, 3)
