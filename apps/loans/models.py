# Utility imports
import calendar
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# Django imports
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

# App imports
from apps.transactions.models import Transaction

# Core imports
from core.enums import Bank

# Constants
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class Loan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    bank = models.CharField(max_length=20, choices=Bank.choices, blank=True, default="")
    contracted_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    iof_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    monthly_interest_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    monthly_cet_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    term_months = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    started_at = models.DateField()
    first_due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at", "-created_at"]
        indexes = [models.Index(fields=["user", "-started_at"], name="loan_user_started_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(contracted_amount__gt=0),
                name="loan_contracted_amount_positive",
            ),
            models.CheckConstraint(condition=Q(iof_amount__gte=0), name="loan_iof_nonnegative"),
            models.CheckConstraint(
                condition=Q(monthly_interest_percentage__gte=0),
                name="loan_monthly_interest_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(term_months__gt=0),
                name="loan_term_months_positive",
            ),
        ]

    @property
    def financed_amount(self):
        return self.contracted_amount + self.iof_amount

    @property
    def monthly_installment_amount(self):
        principal = self.financed_amount
        rate = self.monthly_interest_percentage / Decimal("100")

        if rate == 0:
            payment = principal / self.term_months
        else:
            payment = principal * rate / (Decimal("1") - (Decimal("1") + rate) ** -self.term_months)

        return payment.quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def total_with_interest(self):
        principal = self.financed_amount
        rate = self.monthly_interest_percentage / Decimal("100")

        if rate == 0:
            total = principal
        else:
            payment = principal * rate / (Decimal("1") - (Decimal("1") + rate) ** -self.term_months)
            total = payment * self.term_months

        return total.quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def amount_paid(self):
        return self.installments.aggregate(total=Sum("payments__amount"))["total"] or ZERO

    @property
    def discount_amount(self):
        return (
            self.installments.aggregate(total=Sum("payments__discount_amount"))["total"] or ZERO
        )

    @property
    def remaining_amount(self):
        return max(self.total_with_interest - self.amount_paid - self.discount_amount, ZERO)

    def generate_installments(self):
        if self.installments.exists():
            raise ValueError("O cronograma do empréstimo já foi gerado.")

        regular_amount = self.monthly_installment_amount
        total_amount = self.total_with_interest
        balance = self.financed_amount
        rate = self.monthly_interest_percentage / Decimal("100")
        installments = []

        for number in range(1, self.term_months + 1):
            amount_due = (
                total_amount - regular_amount * (self.term_months - 1)
                if number == self.term_months
                else regular_amount
            )
            interest_amount = (balance * rate).quantize(CENT, rounding=ROUND_HALF_UP)

            if number == self.term_months:
                principal_amount = balance
                interest_amount = amount_due - principal_amount
            else:
                principal_amount = amount_due - interest_amount

            installments.append(
                LoanInstallment(
                    loan=self,
                    number=number,
                    due_date=self._due_date_for(number - 1),
                    amount_due=amount_due,
                    interest_amount=interest_amount,
                    principal_amount=principal_amount,
                )
            )
            balance -= principal_amount

        LoanInstallment.objects.bulk_create(installments)

    def _due_date_for(self, month_offset):
        first_date = self.first_due_date
        month_index = first_date.year * 12 + first_date.month - 1 + month_offset
        year, month_zero_indexed = divmod(month_index, 12)
        month = month_zero_indexed + 1
        day = min(first_date.day, calendar.monthrange(year, month)[1])
        due_date = date(year, month, day)

        while due_date.weekday() >= 5:
            due_date += timedelta(days=1)

        return due_date

    def __str__(self):
        return f"Empréstimo {self.contracted_amount} ({self.get_bank_display()})"


class LoanInstallment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="installments")
    number = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "number"], name="loan_installment_number_unique"
            ),
            models.CheckConstraint(
                condition=Q(number__gt=0), name="loan_installment_number_positive"
            ),
            models.CheckConstraint(
                condition=Q(amount_due__gt=0), name="loan_installment_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(interest_amount__gte=0),
                name="loan_installment_interest_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(principal_amount__gte=0),
                name="loan_installment_principal_nonnegative",
            ),
        ]

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or ZERO

    @property
    def discount_amount(self):
        return self.payments.aggregate(total=Sum("discount_amount"))["total"] or ZERO

    @property
    def remaining_amount(self):
        return max(self.amount_due - self.amount_paid - self.discount_amount, ZERO)

    @property
    def status(self):
        if self.remaining_amount == ZERO:
            return "paid"
        if self.amount_paid > ZERO:
            return "partial"
        if self.due_date < timezone.localdate():
            return "overdue"
        return "pending"

    def __str__(self):
        return f"Parcela {self.number} do empréstimo {self.loan_id}"


class LoanPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    installment = models.ForeignKey(
        LoanInstallment,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    interest_portion = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    principal_portion = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    paid_at = models.DateTimeField()
    expense_transaction = models.OneToOneField(
        Transaction,
        on_delete=models.PROTECT,
        related_name="loan_payment",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="loan_payment_amount_positive"),
            models.CheckConstraint(
                condition=Q(discount_amount__gte=0),
                name="loan_payment_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(interest_portion__gte=0),
                name="loan_payment_interest_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(principal_portion__gte=0),
                name="loan_payment_principal_nonnegative",
            ),
        ]

    def __str__(self):
        return (
            f"Pagamento de {self.amount} da parcela "
            f"{self.installment.number} do empréstimo {self.installment.loan_id}"
        )
