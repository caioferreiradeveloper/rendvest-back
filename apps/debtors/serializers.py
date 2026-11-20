# Utility imports
from decimal import Decimal

# Django imports
from django.utils import timezone
from rest_framework import serializers

# App imports
from apps.debtors.models import Debtor
from core.enums import Bank


class DebtorSerializer(serializers.ModelSerializer):
    is_paid = serializers.BooleanField(read_only=True)
    remaining_amount = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Debtor
        fields = [
            "id",
            "debtor_name",
            "amount",
            "description",
            "occurred_at",
            "paid_amount",
            "paid_at",
            "is_paid",
            "remaining_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "paid_amount",
            "paid_at",
            "is_paid",
            "remaining_amount",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("O valor deve ser maior que zero.")
        return value

    def validate(self, attrs):
        if self.instance is None:
            return attrs

        amount = attrs.get("amount", self.instance.amount)
        if self.instance.paid_amount > amount:
            raise serializers.ValidationError(
                {"amount": "O valor da dívida não pode ser menor que o valor pago."}
            )

        return attrs


class DebtorPaymentSerializer(serializers.Serializer):
    bank = serializers.ChoiceField(choices=Bank.choices, default=Bank.NOT_INFORMED)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_at = serializers.DateTimeField(required=False)

    def validate_paid_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("O valor pago deve ser maior que zero.")
        return value

    def validate(self, attrs):
        debtor = self.context["debtor"]
        paid_amount = attrs["paid_amount"]

        if debtor.is_paid:
            raise serializers.ValidationError({"debtor": "Esta dívida já foi paga."})

        if paid_amount > debtor.amount:
            raise serializers.ValidationError(
                {"paid_amount": "O valor pago não pode ser maior que o valor da dívida."}
            )

        return attrs

    def save(self, **kwargs):
        debtor = self.context["debtor"]
        debtor.paid_amount = self.validated_data["paid_amount"]
        debtor.paid_at = self.validated_data.get("paid_at") or timezone.now()
        debtor.save(update_fields=["paid_amount", "paid_at", "updated_at"])
        return debtor
