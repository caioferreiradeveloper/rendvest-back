from datetime import UTC, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.transactions.models import Transaction

User = get_user_model()


class TransactionApiTests(APITestCase):
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
        self.transaction_url = reverse("transactions:transaction-list")
        self.income_url = reverse("transactions:income-list")
        self.expense_url = reverse("transactions:expense-list")

    def test_income_crud(self):
        create_response = self.client.post(
            self.income_url,
            {
                "amount": "1250.00",
                "bank": Transaction.Bank.NUBANK,
                "category": "Salary",
                "description": "Monthly salary",
                "occurred_at": "2026-11-01T09:00:00Z",
            },
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["type"], Transaction.Type.INCOME)
        self.assertEqual(create_response.data["bank"], Transaction.Bank.NUBANK)
        self.assertEqual(Decimal(create_response.data["amount"]), Decimal("1250.00"))

        transaction_id = create_response.data["id"]
        detail_url = reverse("transactions:income-detail", args=[transaction_id])
        self.assertEqual(self.client.get(self.income_url).data["count"], 1)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)

        update_response = self.client.patch(detail_url, {"amount": "1300.00"})
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(update_response.data["amount"]), Decimal("1300.00"))

        bank_update_response = self.client.patch(
            detail_url,
            {"bank": Transaction.Bank.ITAU},
        )
        self.assertEqual(bank_update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(bank_update_response.data["bank"], Transaction.Bank.ITAU)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Transaction.objects.filter(pk=transaction_id).exists())

    def test_expense_type_is_assigned_by_endpoint_and_amount_must_be_positive(self):
        payload = {
            "amount": "25.50",
            "bank": Transaction.Bank.INTER,
            "category": "Food",
            "occurred_at": datetime(2026, 11, 1, tzinfo=UTC).isoformat(),
            "type": Transaction.Type.INCOME,
        }
        response = self.client.post(self.expense_url, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["type"], Transaction.Type.EXPENSE)
        self.assertEqual(response.data["bank"], Transaction.Bank.INTER)
        self.assertEqual(self.client.get(self.income_url).data["count"], 0)

        payload["amount"] = "0.00"
        invalid_response = self.client.post(self.expense_url, payload)
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_response.data["code"], "RENDVEST_ERROR_0002")
        self.assertEqual(
            invalid_response.data["errors"],
            [{"field": "amount", "message": "O valor deve ser maior que zero."}],
        )

    def test_user_cannot_access_another_users_transaction(self):
        transaction = Transaction.objects.create(
            user=self.other_user,
            type=Transaction.Type.INCOME,
            amount="100.00",
            category="Private",
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
        )

        detail_url = reverse("transactions:income-detail", args=[transaction.pk])
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(self.income_url).data["count"], 0)
        self.assertEqual(self.client.get(self.transaction_url).data["count"], 0)

    def test_list_all_transactions_returns_users_incomes_and_expenses(self):
        income = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.INCOME,
            amount="100.00",
            category="Salary",
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
        expense = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            amount="25.00",
            category="Food",
            occurred_at=datetime(2026, 11, 2, tzinfo=UTC),
        )
        Transaction.objects.create(
            user=self.other_user,
            type=Transaction.Type.INCOME,
            amount="999.00",
            category="Private",
            occurred_at=datetime(2026, 11, 3, tzinfo=UTC),
        )

        response = self.client.get(self.transaction_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {str(income.pk), str(expense.pk)},
        )
        self.assertEqual(
            {item["type"] for item in response.data["results"]},
            {Transaction.Type.INCOME, Transaction.Type.EXPENSE},
        )

    def test_type_bank_filters_transaction_lists(self):
        income = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.INCOME,
            amount="100.00",
            bank=Transaction.Bank.NUBANK,
            category="Salary",
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
        expense = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            amount="25.00",
            bank=Transaction.Bank.INTER,
            category="Food",
            occurred_at=datetime(2026, 11, 2, tzinfo=UTC),
        )

        all_transactions = self.client.get(self.transaction_url, {"type_bank": "nubank"})
        incomes = self.client.get(self.income_url, {"type_bank": "nubank"})
        expenses = self.client.get(self.expense_url, {"type_bank": "inter"})

        self.assertEqual(all_transactions.data["count"], 1)
        self.assertEqual(all_transactions.data["results"][0]["id"], str(income.pk))
        self.assertEqual(incomes.data["count"], 1)
        self.assertEqual(incomes.data["results"][0]["id"], str(income.pk))
        self.assertEqual(expenses.data["count"], 1)
        self.assertEqual(expenses.data["results"][0]["id"], str(expense.pk))

    def test_invalid_bank_returns_error_on_bank_field(self):
        response = self.client.post(
            self.income_url,
            {
                "amount": "50.00",
                "bank": "not-a-bank",
                "category": "Other",
                "occurred_at": datetime(2026, 11, 1, tzinfo=UTC).isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "RENDVEST_ERROR_0002")
        self.assertEqual(response.data["errors"][0]["field"], "bank")
