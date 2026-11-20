import uuid
from calendar import monthrange
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.enums import Type

MIN_AMOUNT = Decimal("0.01")


class Monthly(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monthlies",
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=7, choices=Type.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_invoice = models.BooleanField(default=False)
    invoice = models.ForeignKey(
        "self", on_delete=models.RESTRICT, null=True, blank=True, related_name="recurring_expenses"
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0, is_invoice=False)
                | models.Q(amount=0, is_invoice=True),
                name="monthly_valid_amount",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_invoice=False, invoice__isnull=True)
                    | models.Q(is_invoice=False, type=Type.EXPENSE)
                    | models.Q(is_invoice=True, type=Type.EXPENSE, invoice__isnull=True)
                ),
                name="monthly_invoice_expense_only",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date"))
                | models.Q(end_date__isnull=True),
                name="monthly_valid_dates",
            ),
        ]

    def due_date_for(self, month):
        last_day = monthrange(month.year, month.month)[1]
        due_date = month.replace(day=min(self.start_date.day, last_day))
        if due_date < self.start_date or (self.end_date and due_date > self.end_date):
            return None
        return due_date


class MonthlySettlement(models.Model):
    monthly = models.ForeignKey(Monthly, on_delete=models.CASCADE, related_name="settlements")
    month = models.DateField()
    due_date = models.DateField()
    type = models.CharField(max_length=7, choices=Type.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(MIN_AMOUNT)],
    )
    settled_on = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["monthly", "month"], name="monthly_unique_settlement"),
            models.CheckConstraint(
                condition=models.Q(month__day=1), name="monthly_settlement_month_start"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="monthly_settlement_amount_positive"
            ),
        ]
