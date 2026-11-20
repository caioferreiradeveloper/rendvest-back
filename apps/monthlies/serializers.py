from datetime import date

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.monthlies.invoices import InvoiceField
from apps.monthlies.models import MIN_AMOUNT, Monthly, MonthlySettlement
from core.enums import Bank, Type


def current_month():
    return timezone.localdate().isoformat()[:7]


class MonthQuerySerializer(serializers.Serializer):
    month = serializers.RegexField(
        regex=r"\A[0-9]{4}-(?:0[1-9]|1[0-2])\Z",
        default=current_month,
    )

    def validate_month(self, value):
        try:
            return date.fromisoformat(f"{value}-01")
        except ValueError as exc:
            raise serializers.ValidationError("Informe um mês válido no formato AAAA-MM.") from exc


class MonthlySettlementSerializer(serializers.ModelSerializer):
    month = serializers.SerializerMethodField()

    class Meta:
        model = MonthlySettlement
        fields = ["month", "due_date", "type", "amount", "settled_on"]

    def get_month(self, obj) -> str:
        return obj.month.isoformat()[:7]


class MonthlySerializer(serializers.ModelSerializer):
    invoice = InvoiceField(required=False, allow_null=True)
    invoice_total = serializers.DecimalField(max_digits=24, decimal_places=2, read_only=True)
    month = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    is_settled = serializers.SerializerMethodField()
    settlement = serializers.SerializerMethodField()

    class Meta:
        model = Monthly
        extra_kwargs = {"amount": {"required": False}}
        fields = [
            "id",
            "name",
            "type",
            "amount",
            "is_invoice",
            "invoice",
            "invoice_total",
            "start_date",
            "end_date",
            "month",
            "due_date",
            "is_settled",
            "settlement",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance = self.instance
        start_date = attrs.get("start_date", getattr(instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(instance, "end_date", None))
        if end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "A data de fim deve ser igual ou posterior à data de início."}
            )
        is_invoice = attrs.get("is_invoice", getattr(instance, "is_invoice", False))
        invoice = attrs["invoice"] if "invoice" in attrs else getattr(instance, "invoice_id", None)
        monthly_type = attrs.get("type", getattr(instance, "type", None))
        amount = attrs.get("amount", getattr(instance, "amount", None))
        if instance and is_invoice != instance.is_invoice:
            raise serializers.ValidationError({"is_invoice": "O tipo do cadastro é fixo."})
        if (is_invoice or invoice) and monthly_type != Type.EXPENSE:
            raise serializers.ValidationError({"type": "Faturas só se aplicam a gastos."})
        if is_invoice:
            if invoice:
                raise serializers.ValidationError(
                    {"invoice": "Uma fatura não pode ter outra fatura."}
                )
            if amount is not None and amount != 0:
                raise serializers.ValidationError(
                    {"amount": "O valor da fatura é a soma dos gastos."}
                )
            if instance and (start_date, end_date) != (instance.start_date, instance.end_date):
                if instance.invoice_items.exists() or instance.settlements.exists():
                    raise serializers.ValidationError(
                        {"start_date": "As datas da fatura ficam fixas após o primeiro lançamento."}
                    )
            attrs["amount"] = 0
        elif amount is None or amount < MIN_AMOUNT:
            raise serializers.ValidationError({"amount": "Informe um valor maior que zero."})
        return attrs

    def get_month(self, obj) -> str:
        return self.context["month"].isoformat()[:7]

    @extend_schema_field({"type": "string", "format": "date", "nullable": True})
    def get_due_date(self, obj) -> str | None:
        due_date = (
            obj.month_settlements[0].due_date
            if obj.month_settlements
            else obj.due_date_for(self.context["month"])
        )
        return due_date.isoformat() if due_date else None

    def get_is_settled(self, obj) -> bool:
        return bool(obj.month_settlements)

    @extend_schema_field(MonthlySettlementSerializer(allow_null=True))
    def get_settlement(self, obj):
        if obj.month_settlements:
            return MonthlySettlementSerializer(obj.month_settlements[0]).data
        return None


class MonthlySettlementCreateSerializer(MonthQuerySerializer):
    bank = serializers.ChoiceField(choices=Bank.choices, default=Bank.NOT_INFORMED)
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=MIN_AMOUNT,
        required=False,
    )
    settled_on = serializers.DateField(default=timezone.localdate)
