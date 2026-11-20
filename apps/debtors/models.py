# Utility imports
import uuid
from decimal import Decimal

# Django imports
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

ZERO = Decimal("0.00")


class Debtor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="debtors",
    )
    debtor_name = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        indexes = [models.Index(fields=["user", "-occurred_at"], name="debtor_user_date_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="debtor_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(paid_amount__gte=0),
                name="debtor_paid_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(paid_amount__lte=models.F("amount")),
                name="debtor_paid_amount_lte_amount",
            ),
        ]

    @property
    def is_paid(self):
        return self.paid_at is not None

    @property
    def remaining_amount(self):
        return max(self.amount - self.paid_amount, ZERO)

    def __str__(self):
        return f"{self.debtor_name} - {self.amount}"
