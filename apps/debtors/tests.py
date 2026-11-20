from datetime import UTC, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.debtors.models import Debtor
from apps.transactions.models import Transaction

User = get_user_model()


class DebtorApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePassword123!",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="SecurePassword123!",
        )
        self.client.force_authenticate(self.user)
        self.debtor_list_url = reverse("debtors:debtor-list")
        self.debtor_create_url = reverse("debtors:debtor-create")

    def create_debtor(self, **overrides):
        payload = {
            "debtor_name": "Maria Souza",
            "amount": "250.00",
            "description": "Divida do jantar",
            "occurred_at": "2026-11-01T09:00:00Z",
        }
        payload.update(overrides)
        return self.client.post(self.debtor_create_url, payload, format="json")

    def test_debtor_crud(self):
        create_response = self.create_debtor()

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["debtor_name"], "Maria Souza")
        self.assertEqual(Decimal(create_response.data["amount"]), Decimal("250.00"))
        self.assertEqual(Decimal(create_response.data["paid_amount"]), Decimal("0.00"))
        self.assertFalse(create_response.data["is_paid"])

        debtor_id = create_response.data["id"]
        detail_url = reverse("debtors:debtor-detail", args=[debtor_id])
        update_url = reverse("debtors:debtor-update", args=[debtor_id])
        delete_url = reverse("debtors:debtor-delete", args=[debtor_id])

        self.assertEqual(self.client.get(self.debtor_list_url).data["count"], 1)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)

        update_response = self.client.patch(update_url, {"amount": "300.00"})
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(update_response.data["amount"]), Decimal("300.00"))

        delete_response = self.client.delete(delete_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Debtor.objects.filter(pk=debtor_id).exists())

    def test_payment_marks_debtor_as_paid(self):
        debtor_response = self.create_debtor(amount="250.00")
        payment_url = reverse("debtors:debtor-pay", args=[debtor_response.data["id"]])

        response = self.client.post(
            payment_url,
            {
                "paid_amount": "200.00",
                "paid_at": "2026-11-10T12:00:00Z",
                "bank": "itau",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_paid"])
        self.assertEqual(Decimal(response.data["paid_amount"]), Decimal("200.00"))
        self.assertEqual(Decimal(response.data["remaining_amount"]), Decimal("50.00"))

        debtor = Debtor.objects.get(pk=debtor_response.data["id"])
        self.assertEqual(debtor.paid_amount, Decimal("200.00"))
        self.assertEqual(debtor.paid_at, datetime(2026, 11, 10, 12, tzinfo=UTC))
        entry = Transaction.objects.get(user=self.user)
        self.assertEqual(entry.type, "income")
        self.assertEqual(entry.amount, debtor.paid_amount)
        self.assertEqual(entry.occurred_at, debtor.paid_at)
        self.assertEqual(entry.bank, "itau")

    def test_payment_rejects_non_positive_amount_overpayment_and_repayment(self):
        debtor_response = self.create_debtor(amount="250.00")
        payment_url = reverse("debtors:debtor-pay", args=[debtor_response.data["id"]])

        zero_response = self.client.post(payment_url, {"paid_amount": "0.00"}, format="json")
        overpayment_response = self.client.post(
            payment_url,
            {"paid_amount": "250.01"},
            format="json",
        )
        paid_response = self.client.post(payment_url, {"paid_amount": "250.00"}, format="json")
        repayment_response = self.client.post(payment_url, {"paid_amount": "1.00"}, format="json")

        self.assertEqual(zero_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(zero_response.data["errors"][0]["field"], "paid_amount")
        self.assertEqual(overpayment_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(overpayment_response.data["errors"][0]["field"], "paid_amount")
        self.assertEqual(paid_response.status_code, status.HTTP_200_OK)
        self.assertEqual(repayment_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(repayment_response.data["errors"][0]["field"], "debtor")

    def test_user_cannot_access_another_users_debtor(self):
        debtor = Debtor.objects.create(
            user=self.other_user,
            debtor_name="Private",
            amount="100.00",
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
        )

        detail_url = reverse("debtors:debtor-detail", args=[debtor.pk])
        payment_url = reverse("debtors:debtor-pay", args=[debtor.pk])

        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.post(payment_url, {"paid_amount": "100.00"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.get(self.debtor_list_url).data["count"], 0)
