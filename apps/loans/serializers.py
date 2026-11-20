from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.loans.models import Loan, LoanInstallment, LoanPayment
from core.enums import Bank


class LoanSerializer(serializers.ModelSerializer):
    financed_amount = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    monthly_installment_amount = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    total_with_interest = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    amount_paid = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    discount_amount = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    remaining_amount = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Loan
        fields = [
            "id",
            "bank",
            "contracted_amount",
            "iof_amount",
            "financed_amount",
            "monthly_interest_percentage",
            "monthly_cet_percentage",
            "term_months",
            "started_at",
            "first_due_date",
            "monthly_installment_amount",
            "total_with_interest",
            "amount_paid",
            "discount_amount",
            "remaining_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        started_at = attrs.get("started_at", getattr(self.instance, "started_at", None))
        first_due_date = attrs.get(
            "first_due_date",
            getattr(self.instance, "first_due_date", None),
        )
        if started_at and first_due_date and first_due_date < started_at:
            raise serializers.ValidationError(
                {"first_due_date": "O primeiro vencimento não pode anteceder a contratação."}
            )

        schedule_fields = {
            "contracted_amount",
            "iof_amount",
            "monthly_interest_percentage",
            "term_months",
            "started_at",
            "first_due_date",
        }
        changed_schedule = self.instance and any(
            field in attrs and attrs[field] != getattr(self.instance, field)
            for field in schedule_fields
        )
        if changed_schedule and self.instance.installments.filter(payments__isnull=False).exists():
            raise serializers.ValidationError(
                {
                    "loan": (
                        "Não é possível alterar os valores ou o prazo após registrar pagamentos."
                    )
                }
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        loan = super().create(validated_data)
        loan.generate_installments()
        return loan

    @transaction.atomic
    def update(self, instance, validated_data):
        schedule_fields = {
            "contracted_amount",
            "iof_amount",
            "monthly_interest_percentage",
            "term_months",
            "started_at",
            "first_due_date",
        }
        changed_schedule = any(
            field in validated_data and validated_data[field] != getattr(instance, field)
            for field in schedule_fields
        )

        loan = super().update(instance, validated_data)
        if changed_schedule:
            loan.installments.all().delete()
            loan.generate_installments()
        return loan


class LoanInstallmentSerializer(serializers.ModelSerializer):
    amount_paid = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    discount_amount = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    remaining_amount = serializers.DecimalField(
        max_digits=24,
        decimal_places=2,
        read_only=True,
    )
    status = serializers.CharField(read_only=True)

    class Meta:
        model = LoanInstallment
        fields = [
            "id",
            "number",
            "due_date",
            "amount_due",
            "interest_amount",
            "principal_amount",
            "amount_paid",
            "discount_amount",
            "remaining_amount",
            "status",
        ]
        read_only_fields = fields


class LoanPaymentSerializer(serializers.ModelSerializer):
    bank = serializers.ChoiceField(choices=Bank.choices, required=False, write_only=True)
    installment_number = serializers.IntegerField(min_value=1, write_only=True)
    paid_at = serializers.DateTimeField(required=False)
    interest_portion = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    principal_portion = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    expense_transaction_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = LoanPayment
        fields = [
            "id",
            "installment_number",
            "bank",
            "amount",
            "interest_portion",
            "principal_portion",
            "discount_amount",
            "paid_at",
            "expense_transaction_id",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "interest_portion",
            "principal_portion",
            "discount_amount",
            "expense_transaction_id",
            "created_at",
        ]

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("O valor pago deve ser maior que zero.")
        return value

    def create(self, validated_data):
        validated_data.pop("installment_number")
        validated_data.pop("bank", None)
        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["installment_number"] = instance.installment.number
        return representation
