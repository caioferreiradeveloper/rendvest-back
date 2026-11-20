# Utility imports
import uuid

# Django imports
from django.conf import settings
from django.db import models
from django.db.models import Q

# Core imports
from core.enums import Bank, Type


# Model representing a user's financial transactions, including income and expenses
class Transaction(models.Model):
    # Unique transaction identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Transaction owner
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    # Income or expense type
    type = models.CharField(max_length=10, choices=Type.choices)

    # Transaction amount
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Associated bank
    bank = models.CharField(max_length=20, choices=Bank.choices, blank=True, default="")

    # Transaction category
    category = models.CharField(max_length=80)

    # Additional transaction details
    description = models.TextField(blank=True)

    # Transaction date and time
    occurred_at = models.DateTimeField()

    invoice = models.ForeignKey(
        "monthlies.Monthly",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="invoice_items",
    )
    invoice_month = models.DateField(null=True, blank=True)
    monthly_settlement = models.OneToOneField(
        "monthlies.MonthlySettlement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_transaction",
    )

    # Creation timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    # Last update timestamp
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Default transaction ordering
        ordering = ["-occurred_at", "-created_at"]

        # Optimizes transaction filtering
        indexes = [
            models.Index(fields=["user", "type", "-occurred_at"], name="txn_user_type_date_idx"),
        ]

        # Ensures positive transaction amounts
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="transaction_amount_positive"),
            models.CheckConstraint(
                condition=Q(invoice__isnull=True, invoice_month__isnull=True)
                | Q(
                    invoice__isnull=False,
                    invoice_month__isnull=False,
                    invoice_month__day=1,
                    type=Type.EXPENSE,
                ),
                name="transaction_valid_invoice",
            ),
        ]

    # Returns a readable transaction representation
    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} ({self.category})"
