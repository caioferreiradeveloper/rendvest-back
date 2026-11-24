from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .bolsai import MarketDataUnavailable
from .models import Investment, MarketSnapshot, RealEstateFund


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

    @patch("apps.investments.fund_data.collect_fund")
    def test_fund_views_share_snapshot_and_post_refreshes_immediately(self, collect):
        collect.side_effect = [
            {"prices": [{"close": 100}], "stats": {"volume": 5}},
            {"prices": [{"close": 102}], "stats": {"volume": 8}},
            {"prices": [{"close": 103}], "stats": {"volume": 9}},
        ]
        base = "/api/v1/investments/funds/hglg11"
        self.assertEqual(self.client.get(f"{base}/prices/").json()["prices"][0]["close"], 100)
        self.assertEqual(self.client.get(f"{base}/stats/").json()["volume"], 5)
        collect.assert_called_once()

        self.assertEqual(self.client.post(f"{base}/refresh/").json()["stats"]["volume"], 8)
        self.assertEqual(self.client.get(f"{base}/prices/").json()["prices"][0]["close"], 102)
        self.assertEqual(collect.call_count, 2)

        RealEstateFund.objects.filter(ticker="HGLG11").update(
            updated_at=timezone.now() - timedelta(hours=1)
        )
        call_command("refresh_funds", stdout=StringIO())
        self.assertEqual(self.client.get(f"{base}/stats/").json()["volume"], 9)
        self.assertEqual(collect.call_count, 3)

        collect.side_effect = MarketDataUnavailable()
        self.assertEqual(self.client.post(f"{base}/refresh/").status_code, 503)
        self.assertEqual(self.client.get(f"{base}/stats/").json()["volume"], 9)

    @patch("apps.investments.catalog.fetch_brapi")
    def test_search_and_refresh_use_the_same_fii_catalog(self, fetch):
        fetch.return_value = {
            "stocks": [
                {"stock": "HGLG11", "subType": "fii", "name": "Pátria Log"},
                {"stock": "AAZQ11", "subType": "fi-agro"},
                {"stock": "BOVA11", "subType": "etf"},
            ]
        }
        response = self.client.get("/api/v1/investments/assets/?type=fii")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([asset["ticker"] for asset in response.json()["results"]], ["HGLG11"])
        response = self.client.post("/api/v1/investments/funds/aazq11/refresh/")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(RealEstateFund.objects.filter(pk="AAZQ11").exists())
        fetch.assert_called_once_with("quote/list?type=fund&subType=fii")

    @patch("apps.investments.fund_data.get_market_data")
    @patch("apps.investments.fund_data.fetch_brapi")
    @patch("apps.investments.fund_data.list_funds")
    def test_fund_uses_bolsai_when_brapi_returns_incomplete_data(self, catalog, brapi, bolsai):
        catalog.return_value = [{"ticker": "HTMX11", "name": "Hotel Maxinvest", "segment": "Hotel"}]
        brapi.side_effect = {
            "quote/HTMX11?range=3mo&interval=1d": {"results": [{"symbol": "HTMX11"}]},
            "v2/fii/indicators?symbols=HTMX11": {},
            "v2/fii/dividends?symbols=HTMX11": {
                "dividends": [
                    {
                        "symbol": "HTMX11",
                        "label": "RENDIMENTO",
                        "paymentDate": "2026-11-16",
                        "rawRate": 1.25,
                    }
                ]
            },
        }.__getitem__
        responses = {
            "stocks/HTMX11/quote": {"close": 130, "trade_date": "2026-11-20"},
            "stocks/HTMX11/history?limit=270": {
                "prices": [{"close": 131, "trade_date": "2026-11-19"}],
            },
            "fiis/HTMX11": {},
            "fiis/HTMX11/distributions?years=2": {"payments": []},
            "dividends/HTMX11?years=2": {
                "payments": [
                    {
                        "type": "Rendimento",
                        "payment_date": "2026-11-16",
                        "record_date": "2026-10-30",
                        "value_per_share": 1.25,
                    }
                ]
            },
        }
        bolsai.side_effect = lambda path, **kwargs: responses[path]
        base = "/api/v1/investments/funds/HTMX11"
        self.assertEqual(self.client.get(f"{base}/quote/").json()["price"], "130.0000")
        self.assertEqual(self.client.get(f"{base}/prices/").json()["prices"][0]["close"], 131)
        payments = self.client.get(f"{base}/distributions/").json()["payments"]
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0]["record_date"], "2026-10-30")


class InvestmentTests(APITestCase):
    url = "/api/v1/investments/"
    purchase = {
        "asset": "hglg11",
        "amount": "250.75",
        "invested_at": "2025-01-02",
        "quantity": 2,
    }

    def setUp(self):
        self.user = get_user_model().objects.create(email="investor@example.com")
        self.client.force_authenticate(self.user)
        cache.clear()

    @patch("apps.investments.serializers.list_funds", return_value=[{"ticker": "HGLG11"}])
    def test_records_purchase_and_lists_only_users_fiis(self, _list_funds):
        response = self.client.post(self.url, self.purchase, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["quantity"], 2)
        self.assertEqual(response.data["amount"], "250.75")
        self.assertEqual(response.data["type"], "fii")
        self.assertEqual(response.data["asset"], "HGLG11")

        Investment.objects.create(
            user=self.user, type="stock", asset="PETR4", amount="100", invested_at="2025-01-02"
        )
        Investment.objects.create(
            user=self.user, type="fii", asset="KNRI11", amount="100", invested_at="2025-01-01"
        )
        result = self.client.get(self.url).json()
        self.assertEqual(
            [(item["asset"], item["quantity"]) for item in result],
            [
                ("HGLG11", 2),
                ("KNRI11", None),
            ],
        )
        other = get_user_model().objects.create(email="other@example.com")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(self.url).json(), [])
        self.assertEqual(APIClient().get(self.url).status_code, 401)

    @patch("apps.investments.serializers.list_funds", return_value=[{"ticker": "HGLG11"}])
    def test_rejects_other_assets_and_invalid_purchase_data(self, _list_funds):
        for overrides in (
            {"quantity": None},
            {"quantity": 0},
            {"quantity": -1},
            {"quantity": 1.5},
            {"type": "stock"},
            {"type": "treasury"},
            {"asset": "PETR4"},
            {"asset": "BOVA11"},
            {"amount": "0"},
            {"invested_at": (timezone.localdate() + timedelta(days=1)).isoformat()},
        ):
            with self.subTest(overrides=overrides):
                response = self.client.post(self.url, self.purchase | overrides, format="json")
                self.assertEqual(response.status_code, 400, response.data)
        missing_quantity = {key: value for key, value in self.purchase.items() if key != "quantity"}
        self.assertEqual(
            self.client.post(self.url, missing_quantity, format="json").status_code, 400
        )
        self.assertEqual(self.client.get(self.url).json(), [])
