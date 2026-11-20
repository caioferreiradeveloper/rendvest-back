# Django imports
from django.utils import timezone
from rest_framework import serializers

# App imports
from apps.monthlies.invoices import InvoiceField, validate_open_invoice
from apps.monthlies.models import Monthly
from apps.transactions.models import Transaction
from core.enums import Type


# Serializer responsible for validating new user transactions
class TransactionSerializer(serializers.ModelSerializer):
    invoice = InvoiceField(required=False, allow_null=True)
    invoice_month = serializers.DateField(
        format="%Y-%m", input_formats=["%Y-%m"], required=False, allow_null=True
    )

    class Meta:
        model = Transaction
        fields = [
            "id",
            "type",
            "amount",
            "bank",
            "category",
            "description",
            "occurred_at",
            "invoice",
            "invoice_month",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    # Ensures the transaction amount is positive
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("O valor deve ser maior que zero.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.monthly_settlement_id:
            raise serializers.ValidationError(
                "Este lançamento foi gerado pela baixa da mensalidade."
            )

        old_invoice_id = getattr(instance, "invoice_id", None)
        invoice_id = old_invoice_id
        if "invoice" in attrs:
            invoice_id = attrs["invoice"].pk if attrs["invoice"] else None

        month = attrs.get("invoice_month")
        if invoice_id is None and month:
            raise serializers.ValidationError({"invoice_month": "Selecione uma fatura."})
        if not (old_invoice_id or invoice_id):
            return attrs

        invoices = {
            invoice.pk: invoice
            for invoice in Monthly.objects.filter(
                pk__in={pk for pk in (old_invoice_id, invoice_id) if pk is not None},
                user=self.context["request"].user,
                is_invoice=True,
            )
            .order_by("pk")
            .select_for_update()
        }
        if old_invoice_id:
            validate_open_invoice(invoices[old_invoice_id], instance.invoice_month)

        if invoice_id is None:
            attrs["invoice_month"] = None
            return attrs

        if attrs.get("type", getattr(instance, "type", None)) != Type.EXPENSE:
            raise serializers.ValidationError({"invoice": "Somente gastos podem entrar na fatura."})
        invoice = invoices.get(invoice_id)
        if invoice is None:
            raise serializers.ValidationError({"invoice": "Fatura indisponível."})
        if "invoice_month" not in attrs and invoice_id == old_invoice_id:
            month = instance.invoice_month
        if month is None:
            occurred_at = attrs.get("occurred_at", getattr(instance, "occurred_at", None))
            month = timezone.localdate(occurred_at).replace(day=1)
        validate_open_invoice(invoice, month)
        attrs["invoice_month"] = month
        return attrs
