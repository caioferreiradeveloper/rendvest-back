from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.loans.models import Loan, LoanInstallment, LoanPayment
from apps.transactions.models import Transaction

User = get_user_model()


class LoanApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="borrower@example.com",
            password="SecurePassword123!",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="SecurePassword123!",
        )
        self.client.force_authenticate(self.user)
        self.loan_list_url = reverse("loans:loan-list")

    def create_loan(self, **overrides):
        payload = {
            "bank": Transaction.Bank.NUBANK,
            "contracted_amount": "8000.00",
            "iof_amount": "117.98",
            "monthly_interest_percentage": "8.4500",
            "monthly_cet_percentage": "8.8880",
            "term_months": 7,
            "started_at": "2026-09-30",
            "first_due_date": "2026-10-30",
        }
        payload.update(overrides)
        return self.client.post(self.loan_list_url, payload, format="json")

    def test_type_bank_filters_loan_list(self):
        nubank_loan = self.create_loan()
        itau_loan = self.create_loan(bank=Transaction.Bank.ITAU)

        response = self.client.get(self.loan_list_url, {"type_bank": "itau"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], itau_loan.data["id"])
        self.assertNotEqual(response.data["results"][0]["id"], nubank_loan.data["id"])

    def installments_url(self, loan_id):
        return reverse("loans:installment-list", kwargs={"loan_pk": loan_id})

    def payments_url(self, loan_id):
        return reverse("loans:payment-list", kwargs={"loan_pk": loan_id})

    def test_contract_creates_price_schedule_including_iof(self):
        response = self.create_loan()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["bank"], Transaction.Bank.NUBANK)
        self.assertEqual(Decimal(response.data["financed_amount"]), Decimal("8117.98"))
        self.assertEqual(Decimal(response.data["monthly_installment_amount"]), Decimal("1583.32"))
        self.assertEqual(Decimal(response.data["total_with_interest"]), Decimal("11083.23"))

        installments = LoanInstallment.objects.filter(loan_id=response.data["id"])
        self.assertEqual(installments.count(), 7)
        self.assertEqual(
            sum(installments.values_list("amount_due", flat=True)),
            Decimal("11083.23"),
        )
        self.assertEqual(installments.get(number=7).amount_due, Decimal("1583.31"))
        self.assertEqual(
            list(installments.values_list("due_date", flat=True)),
            [
                date(2026, 10, 30),
                date(2026, 11, 30),
                date(2026, 12, 30),
                date(2027, 2, 1),
                date(2027, 3, 1),
                date(2027, 3, 30),
                date(2027, 4, 30),
            ],
        )

        schedule_response = self.client.get(self.installments_url(response.data["id"]))
        self.assertEqual(schedule_response.status_code, status.HTTP_200_OK)
        self.assertEqual(schedule_response.data["count"], 7)

    def test_zero_interest_schedule_divides_principal_and_adjusts_last_cent(self):
        response = self.create_loan(
            contracted_amount="1000.00",
            iof_amount="0.00",
            monthly_interest_percentage="0",
            monthly_cet_percentage=None,
            term_months=3,
            started_at="2026-01-01",
            first_due_date="2026-02-01",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data["total_with_interest"]), Decimal("1000.00"))
        self.assertEqual(
            list(
                LoanInstallment.objects.filter(loan_id=response.data["id"]).values_list(
                    "amount_due",
                    flat=True,
                )
            ),
            [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")],
        )

    def test_partial_payment_creates_matching_expense_and_does_not_change_other_installments(
        self,
    ):
        loan_response = self.create_loan()
        loan_id = loan_response.data["id"]
        payment_url = self.payments_url(loan_id)
        installments_url = self.installments_url(loan_id)
        original_second_installment = LoanInstallment.objects.get(loan_id=loan_id, number=2)
        original_amount = original_second_installment.amount_due

        response = self.client.post(
            payment_url,
            {
                "installment_number": 1,
                "amount": "897.00",
                "paid_at": "2026-10-30T12:00:00Z",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["installment_number"], 1)
        self.assertEqual(Decimal(response.data["amount"]), Decimal("897.00"))
        self.assertEqual(Decimal(response.data["interest_portion"]), Decimal("685.97"))
        self.assertEqual(Decimal(response.data["principal_portion"]), Decimal("211.03"))

        payment = LoanPayment.objects.get(pk=response.data["id"])
        expense = payment.expense_transaction
        self.assertEqual(expense.user, self.user)
        self.assertEqual(expense.type, Transaction.Type.EXPENSE)
        self.assertEqual(expense.bank, Transaction.Bank.NUBANK)
        self.assertEqual(expense.category, "Pagamento de empréstimo")
        self.assertEqual(expense.amount, Decimal("897.00"))

        installment = self.client.get(installments_url).data["results"][0]
        self.assertEqual(installment["status"], "partial")
        self.assertEqual(Decimal(installment["amount_paid"]), Decimal("897.00"))
        self.assertEqual(Decimal(installment["remaining_amount"]), Decimal("686.32"))
        self.assertEqual(
            LoanInstallment.objects.get(loan_id=loan_id, number=2).amount_due,
            original_amount,
        )

        loan_detail = self.client.get(reverse("loans:loan-detail", kwargs={"pk": loan_id}))
        self.assertEqual(Decimal(loan_detail.data["amount_paid"]), Decimal("897.00"))
        self.assertEqual(Decimal(loan_detail.data["remaining_amount"]), Decimal("10186.23"))

    def test_partial_payments_complete_only_the_selected_installment(self):
        loan_response = self.create_loan()
        loan_id = loan_response.data["id"]
        payment_url = self.payments_url(loan_id)

        first_payment = self.client.post(
            payment_url,
            {"installment_number": 1, "amount": "897.00"},
            format="json",
        )
        second_payment = self.client.post(
            payment_url,
            {"installment_number": 1, "amount": "686.32"},
            format="json",
        )

        self.assertEqual(first_payment.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_payment.status_code, status.HTTP_201_CREATED)
        installment = LoanInstallment.objects.get(loan_id=loan_id, number=1)
        self.assertEqual(installment.status, "paid")
        self.assertEqual(installment.amount_paid, Decimal("1583.32"))
        self.assertEqual(
            LoanInstallment.objects.get(loan_id=loan_id, number=2).status,
            "pending",
        )
        payment_list = self.client.get(payment_url)
        self.assertEqual(payment_list.data["count"], 2)
        self.assertEqual(
            [payment["installment_number"] for payment in payment_list.data["results"]],
            [1, 1],
        )

    def test_payment_rejects_non_positive_amount_and_overpayment(self):
        loan_response = self.create_loan()
        payment_url = self.payments_url(loan_response.data["id"])

        zero_response = self.client.post(
            payment_url,
            {"installment_number": 1, "amount": "0.00"},
            format="json",
        )
        overpayment_response = self.client.post(
            payment_url,
            {"installment_number": 1, "amount": "1583.33"},
            format="json",
        )

        self.assertEqual(zero_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(zero_response.data["errors"][0]["field"], "amount")
        self.assertEqual(overpayment_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(overpayment_response.data["errors"][0]["field"], "amount")
        self.assertEqual(LoanPayment.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_payment_rejects_unknown_installment(self):
        loan_response = self.create_loan()

        response = self.client.post(
            self.payments_url(loan_response.data["id"]),
            {"installment_number": 8, "amount": "100.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(LoanPayment.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_first_due_date_cannot_precede_loan_start(self):
        response = self.create_loan(first_due_date="2026-09-29")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["errors"][0]["field"], "first_due_date")
        self.assertEqual(Loan.objects.count(), 0)

    def test_user_cannot_access_another_users_loan_installments_or_payments(self):
        loan = Loan.objects.create(
            user=self.other_user,
            bank=Transaction.Bank.ITAU,
            contracted_amount="1000.00",
            iof_amount="0.00",
            monthly_interest_percentage="1.0000",
            term_months=10,
            started_at=date(2026, 1, 1),
            first_due_date=date(2026, 2, 1),
        )
        detail_url = reverse("loans:loan-detail", kwargs={"pk": loan.pk})

        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get(self.installments_url(loan.pk)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(self.payments_url(loan.pk)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.get(self.loan_list_url).data["count"], 0)

    def test_cannot_delete_loan_with_payment_history(self):
        loan_response = self.create_loan()
        loan_id = loan_response.data["id"]
        payment_response = self.client.post(
            self.payments_url(loan_id),
            {"installment_number": 1, "amount": "100.00"},
            format="json",
        )
        self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED)

        detail_url = reverse("loans:loan-detail", kwargs={"pk": loan_id})
        response = self.client.delete(detail_url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "RENDVEST_ERROR_0007")
        self.assertTrue(Loan.objects.filter(pk=loan_id).exists())
