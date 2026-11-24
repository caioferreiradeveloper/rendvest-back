from django.conf import settings
from django.db import models


class MarketSnapshot(models.Model):
    endpoint = models.CharField(max_length=120, primary_key=True)
    data = models.JSONField(null=True)
    fetched_at = models.DateTimeField(null=True)


class RealEstateFund(models.Model):
    ticker = models.CharField(max_length=6, primary_key=True)
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(null=True, db_index=True)


class Investment(models.Model):
    class Type(models.TextChoices):
        STOCK = "stock", "Ação"
        FII = "fii", "FII"
        TREASURY = "treasury", "Tesouro Direto"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=8, choices=Type.choices)
    asset = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    invested_at = models.DateField()
    maturity_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-invested_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__isnull=True) | models.Q(quantity__gt=0, type="fii"),
                name="investment_fii_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="investment_amount_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        type="treasury",
                        maturity_date__isnull=False,
                        maturity_date__gte=models.F("invested_at"),
                    )
                    | (~models.Q(type="treasury") & models.Q(maturity_date__isnull=True))
                ),
                name="investment_maturity_valid",
            ),
        ]
