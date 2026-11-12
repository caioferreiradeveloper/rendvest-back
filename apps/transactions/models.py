import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Transaction(models.Model):
    class Type(models.TextChoices):
        INCOME = "income", "Ganho"
        EXPENSE = "expense", "Gasto"

    class Bank(models.TextChoices):
        NOT_INFORMED = "", "Não informado"
        BANCO_DO_BRASIL = "banco_do_brasil", "Banco do Brasil"
        BRADESCO = "bradesco", "Bradesco"
        BTG_PACTUAL = "btg_pactual", "BTG Pactual"
        C6_BANK = "c6_bank", "C6 Bank"
        CAIXA = "caixa", "Caixa Econômica Federal"
        INTER = "inter", "Banco Inter"
        ITAU = "itau", "Itaú Unibanco"
        MERCADO_PAGO = "mercado_pago", "Mercado Pago"
        NUBANK = "nubank", "Nubank"
        PAGBANK = "pagbank", "PagBank"
        PICPAY = "picpay", "PicPay"
        SANTANDER = "santander", "Santander"
        SICOOB = "sicoob", "Sicoob"
        SICREDI = "sicredi", "Sicredi"
        OTHER = "other", "Outro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bank = models.CharField(max_length=20, choices=Bank.choices, blank=True, default="")
    category = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "type", "-occurred_at"], name="txn_user_type_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="transaction_amount_positive"),
        ]

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} ({self.category})"
