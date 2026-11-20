from rest_framework import serializers

from apps.monthlies.models import Monthly


class InvoiceField(serializers.PrimaryKeyRelatedField):
    def __init__(self, **kwargs):
        super().__init__(queryset=Monthly.objects.none(), **kwargs)

    def get_queryset(self):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Monthly.objects.filter(user=request.user, is_invoice=True)
        return super().get_queryset()


def validate_open_invoice(invoice, month):
    if invoice.due_date_for(month) is None:
        raise serializers.ValidationError({"invoice_month": "A fatura não vence neste mês."})
    if invoice.settlements.filter(month=month).exists():
        raise serializers.ValidationError({"invoice_month": "A fatura deste mês já foi paga."})
