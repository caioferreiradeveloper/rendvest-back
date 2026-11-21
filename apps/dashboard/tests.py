from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.debtors.models import Debtor
from apps.loans.models import Loan, LoanPayment
from apps.monthlies.models import Monthly, MonthlySettlement
from apps.transactions.models import Transaction
from apps.wishlist.models import WishlistItem
from core.enums import Type


class DashboardTests(APITestCase):
    def test_dashboard_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 401)

    def test_dashboard_cash_flow_and_kpis_use_only_the_current_user(self):
        user = get_user_model().objects.create_user(email="dashboard@example.com")
        other = get_user_model().objects.create_user(email="other@example.com")
        self.client.force_authenticate(user)
        now = timezone.make_aware(datetime(2026, 1, 20, 12))
        month = date(2026, 1, 1)
        today = now.date()

        def transaction(kind, amount, **overrides):
            return Transaction.objects.create(
                **{
                    "user": user,
                    "type": kind,
                    "amount": amount,
                    "category": "Teste",
                    "occurred_at": now,
                    **overrides,
                }
            )

        transaction(Type.INCOME, "800", bank="itau")
        transaction(Type.INCOME, "200", occurred_at=now - timedelta(days=31))
        transaction(Type.INCOME, "900", occurred_at=now - timedelta(days=220))
        transaction(Type.INCOME, "5000", user=other)
        transaction(Type.INCOME, "5000", occurred_at=now + timedelta(days=1))
        invoice = Monthly.objects.create(
            user=user,
            name="Cartão",
            type=Type.EXPENSE,
            amount=0,
            is_invoice=True,
            start_date=month,
        )
        transaction(Type.EXPENSE, "100", invoice=invoice, invoice_month=month)
        settlement = MonthlySettlement.objects.create(
            monthly=invoice,
            month=month,
            due_date=month,
            type=Type.EXPENSE,
            amount=100,
            settled_on=today,
        )
        transaction(Type.EXPENSE, "100", monthly_settlement=settlement)
        Monthly.objects.create(
            user=user,
            name="Internet",
            type=Type.EXPENSE,
            amount=70,
            start_date=month,
        )
        Monthly.objects.create(
            user=user,
            name="Renda recorrente",
            type=Type.INCOME,
            amount=40,
            start_date=month,
        )

        loan = Loan.objects.create(
            user=user,
            contracted_amount=Decimal("200"),
            monthly_interest_percentage=Decimal("0"),
            term_months=1,
            started_at=month,
            first_due_date=month,
        )
        loan.generate_installments()
        LoanPayment.objects.create(
            installment=loan.installments.get(),
            amount=50,
            discount_amount=10,
            paid_at=now,
            expense_transaction=transaction(Type.EXPENSE, "50"),
        )
        Debtor.objects.create(user=user, debtor_name="Pessoa", amount=120, occurred_at=now)
        Debtor.objects.create(
            user=user,
            debtor_name="Quitado",
            amount=40,
            occurred_at=now,
            paid_amount=40,
            paid_at=now,
        )
        transaction(Type.INCOME, "40")
        WishlistItem.objects.create(
            user=user, name="Livro", amount=90, expected_purchase_date=today
        )
        WishlistItem.objects.create(user=other, name="Outro item", amount=90)

        with patch("apps.dashboard.metrics.timezone.now", return_value=now):
            response = self.client.get(reverse("dashboard"))
            filtered = self.client.get(reverse("dashboard"), {"bank": "itau"})

        self.assertEqual(response.status_code, 200)
        summary = response.json()
        self.assertEqual(
            summary["transactions"],
            {
                "balance": "1790.00",
                "income": "840.00",
                "expenses": "150.00",
                "net": "690.00",
                "transaction_count": 4,
            },
        )
        self.assertEqual(len(summary["history"]), 6)
        self.assertEqual(summary["history"][-2]["month"], "2025-12-01")
        self.assertEqual(summary["history"][-2]["net"], "200.00")
        self.assertEqual(
            summary["loans"],
            {
                "active_count": 1,
                "outstanding": "140.00",
                "paid_this_month": "50.00",
                "overdue_installments": 1,
            },
        )
        self.assertEqual(
            summary["debtors"],
            {
                "outstanding": "120.00",
                "open_count": 1,
                "received_this_month": "40.00",
            },
        )
        self.assertEqual(
            summary["wishlist"],
            {
                "count": 1,
                "total": "90.00",
                "planned_this_month": "90.00",
            },
        )
        self.assertEqual(
            summary["monthlies"],
            {
                "settled_count": 1,
                "pending_count": 2,
                "pending_income": "40.00",
                "pending_expenses": "70.00",
            },
        )
        self.assertEqual(filtered.json()["transactions"]["balance"], "800.00")
        self.assertEqual(filtered.json()["loans"], summary["loans"])
