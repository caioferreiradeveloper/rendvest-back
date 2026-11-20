from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.monthlies.models import MonthlySettlement
from apps.transactions.models import Transaction


class MonthlyApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="owner@example.com")
        self.client.force_authenticate(self.user)

    def create_monthly(self, **overrides):
        response = self.client.post(
            reverse("monthlies:monthly-create"),
            {
                "name": "Assinatura",
                "type": "expense",
                "amount": "50.00",
                "start_date": "2026-01-31",
                **overrides,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def test_monthly_settlement_is_unique_and_preserves_historical_amount(self):
        pk = self.create_monthly()
        settle_url = reverse("monthlies:monthly-settle", args=[pk])
        detail_url = reverse("monthlies:monthly-detail", args=[pk])
        update_url = reverse("monthlies:monthly-update", args=[pk])

        invalid = self.client.post(settle_url, {"month": "2026-02", "bank": "invalid"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.data["errors"][0]["field"], "bank")
        response = self.client.post(
            settle_url,
            {
                "month": "2026-02",
                "amount": "55.00",
                "settled_on": "2026-03-01",
                "bank": "nubank",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["due_date"], "2026-02-28")
        self.assertEqual(response.data["settled_on"], "2026-03-01")
        self.assertEqual(response.data["amount"], "55.00")
        self.assertEqual(self.client.post(settle_url, {"month": "2026-02"}).status_code, 400)

        entry = Transaction.objects.get(user=self.user)
        self.assertEqual(entry.type, "expense")
        self.assertEqual(str(entry.amount), "55.00")
        self.assertEqual(timezone.localdate(entry.occurred_at).isoformat(), "2026-03-01")
        transactions = self.client.get(reverse("transactions:transaction-list")).data
        self.assertEqual(transactions["results"][0]["id"], str(entry.pk))
        self.assertEqual(transactions["results"][0]["bank"], "nubank")

        response = self.client.patch(update_url, {"amount": "60.00"})
        self.assertEqual(response.status_code, 200, response.data)
        february = self.client.get(detail_url, {"month": "2026-02"}).data
        self.assertTrue(february["is_settled"])
        self.assertEqual(february["settlement"]["amount"], "55.00")

        march = self.client.get(detail_url, {"month": "2026-03"}).data
        self.assertFalse(march["is_settled"])
        self.assertEqual(march["due_date"], "2026-03-31")
        self.assertIsNone(march["settlement"])
        response = self.client.post(settle_url, {"month": "2026-03"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "60.00")
        self.assertTrue(Transaction.objects.filter(user=self.user, bank="", amount=60).exists())
        self.assertEqual(MonthlySettlement.objects.count(), 2)

    def test_end_date_and_user_scope(self):
        pk = self.create_monthly(name="Salário", type="income", end_date="2026-02-28")
        settle_url = reverse("monthlies:monthly-settle", args=[pk])
        list_url = reverse("monthlies:monthly-list")
        update_url = reverse("monthlies:monthly-update", args=[pk])
        self.assertEqual(
            self.client.patch(update_url, {"end_date": "2026-01-01"}).status_code,
            400,
        )
        for month in ["2025-12", "2026-03", "2026-13"]:
            with self.subTest(month=month):
                self.assertEqual(self.client.post(settle_url, {"month": month}).status_code, 400)

        response = self.client.post(settle_url, {"month": "2026-02"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["type"], "income")
        self.assertEqual(Transaction.objects.get(user=self.user).type, "income")
        response = self.client.get(list_url, {"month": "2026-02", "type": "income"})
        self.assertEqual(response.data["count"], 1)
        self.assertTrue(response.data["results"][0]["is_settled"])

        other_user = get_user_model().objects.create_user(email="other@example.com")
        self.client.force_authenticate(other_user)
        self.assertEqual(self.client.get(list_url).data["count"], 0)
        self.assertEqual(self.client.post(settle_url, {"month": "2026-01"}).status_code, 404)

    def create_invoice(self):
        response = self.client.post(
            reverse("monthlies:monthly-create"),
            {
                "name": "Fatura do cartão",
                "type": "expense",
                "is_invoice": True,
                "start_date": "2026-01-10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["invoice_total"], "0.00")
        return response.data["id"]

    def test_invoice_counts_direct_and_recurring_expenses_only_after_payment(self):
        invoice = self.create_invoice()
        transaction_create = reverse("transactions:transaction-create")
        transaction_list = reverse("transactions:transaction-list")
        invoice_detail = reverse("monthlies:monthly-detail", args=[invoice])
        invoice_payment = reverse("monthlies:monthly-settle", args=[invoice])
        expense = {
            "type": "expense",
            "amount": "100.00",
            "category": "Mercado",
            "occurred_at": "2026-03-01T12:00:00Z",
            "invoice": invoice,
        }
        direct = self.client.post(transaction_create, expense, format="json")
        self.assertEqual(direct.status_code, 201, direct.data)
        self.assertEqual(direct.data["invoice_month"], "2026-03")

        monthly = self.create_monthly(invoice=invoice)
        response = self.client.post(
            reverse("monthlies:monthly-settle", args=[monthly]),
            {"month": "2026-03", "amount": "60.00", "settled_on": "2026-04-01"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get(transaction_list).data["count"], 0)
        items = self.client.get(transaction_list, {"invoice": invoice, "invoice_month": "2026-03"})
        self.assertEqual(items.data["count"], 2)
        march = self.client.get(invoice_detail, {"month": "2026-03"})
        self.assertEqual(march.data["invoice_total"], "160.00")
        april = self.client.get(invoice_detail, {"month": "2026-04"})
        self.assertEqual(april.data["invoice_total"], "0.00")

        response = self.client.post(invoice_payment, {"month": "2026-03", "amount": "100.00"})
        self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post(invoice_payment, {"month": "2026-03", "bank": "nubank"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "160.00")
        entries = self.client.get(transaction_list).data
        self.assertEqual(entries["count"], 1)
        self.assertEqual(entries["results"][0]["amount"], "160.00")
        self.assertEqual(entries["results"][0]["bank"], "nubank")

        self.assertEqual(self.client.post(invoice_payment, {"month": "2026-03"}).status_code, 400)
        self.assertEqual(
            self.client.post(transaction_create, expense, format="json").status_code, 400
        )
        delete = reverse("transactions:transaction-delete", args=[direct.data["id"]])
        self.assertEqual(self.client.delete(delete).status_code, 400)

    def test_invoice_associations_require_expenses_and_same_owner(self):
        invoice = self.create_invoice()
        create = reverse("transactions:transaction-create")
        payload = {
            "type": "income",
            "amount": "100.00",
            "category": "Teste",
            "occurred_at": "2026-03-01T12:00:00Z",
            "invoice": invoice,
        }
        response = self.client.post(create, payload, format="json")
        self.assertEqual(response.status_code, 400)
        other = get_user_model().objects.create_user(email="invoice-other@example.com")
        self.client.force_authenticate(other)
        response = self.client.post(create, {**payload, "type": "expense"}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("monthlies:monthly-create"),
            {
                "name": "Assinatura",
                "type": "expense",
                "start_date": "2026-03-01",
                "amount": "50.00",
                "invoice": invoice,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
