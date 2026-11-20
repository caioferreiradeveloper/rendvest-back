from datetime import datetime, time
from decimal import Decimal

from django.db import transaction
from django.db.models import Case, DecimalField, OuterRef, Prefetch, Subquery, Sum, When
from django.db.models.deletion import RestrictedError
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.response import Response

from apps.monthlies.invoices import validate_open_invoice
from apps.monthlies.models import Monthly, MonthlySettlement
from apps.monthlies.serializers import (
    MonthlySerializer,
    MonthlySettlementCreateSerializer,
    MonthlySettlementSerializer,
    MonthQuerySerializer,
)
from apps.transactions.models import Transaction


class MonthlyQuerysetMixin:
    queryset = Monthly.objects.none()

    def get_queryset(self):
        return Monthly.objects.filter(user=self.request.user)


class MonthlyStatusMixin(MonthlyQuerysetMixin):
    serializer_class = MonthlySerializer

    def get_month(self):
        if not hasattr(self, "month"):
            serializer = MonthQuerySerializer(data=self.request.query_params)
            serializer.is_valid(raise_exception=True)
            self.month = serializer.validated_data["month"]
        return self.month

    def get_queryset(self):
        month = self.get_month()
        totals = (
            Transaction.objects.filter(invoice=OuterRef("pk"), invoice_month=month)
            .order_by()
            .values("invoice")
            .annotate(total=Sum("amount"))
            .values("total")
        )
        amount_field = DecimalField(max_digits=24, decimal_places=2)
        return (
            super()
            .get_queryset()
            .annotate(
                invoice_total=Case(
                    When(
                        is_invoice=True,
                        then=Coalesce(Subquery(totals), Decimal("0.00"), output_field=amount_field),
                    ),
                    output_field=amount_field,
                )
            )
            .prefetch_related(
                Prefetch(
                    "settlements",
                    queryset=MonthlySettlement.objects.filter(month=month),
                    to_attr="month_settlements",
                )
            )
        )

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "month": self.get_month()}


@extend_schema(parameters=[MonthQuerySerializer])
class MonthlyList(MonthlyStatusMixin, generics.ListAPIView):
    filterset_fields = ["type", "is_invoice"]
    ordering_fields = ["name", "amount", "start_date", "created_at"]


@extend_schema(parameters=[MonthQuerySerializer])
class MonthlyCreate(MonthlyStatusMixin, generics.CreateAPIView):
    def perform_create(self, serializer):
        monthly = serializer.save(user=self.request.user)
        monthly.month_settlements = []
        monthly.invoice_total = Decimal("0.00") if monthly.is_invoice else None


@extend_schema(parameters=[MonthQuerySerializer])
class MonthlyDetail(MonthlyStatusMixin, generics.RetrieveAPIView):
    pass


@extend_schema(parameters=[MonthQuerySerializer])
class MonthlyUpdate(MonthlyStatusMixin, generics.UpdateAPIView):
    def get_queryset(self):
        return super().get_queryset().select_for_update()

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)


class MonthlyDelete(MonthlyQuerysetMixin, generics.DestroyAPIView):
    serializer_class = MonthlySerializer

    def get_queryset(self):
        return super().get_queryset().select_for_update()

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.is_invoice and instance.settlements.exists():
            raise serializers.ValidationError(
                {"invoice": "A fatura possui pagamentos registrados."}
            )
        try:
            instance.delete()
        except RestrictedError as exc:
            raise serializers.ValidationError(
                {"invoice": "A fatura possui gastos vinculados."}
            ) from exc


class MonthlySettle(MonthlyQuerysetMixin, generics.GenericAPIView):
    serializer_class = MonthlySettlementCreateSerializer

    def get_queryset(self):
        return super().get_queryset().select_for_update()

    @extend_schema(responses={201: MonthlySettlementSerializer})
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        monthly = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        month = data["month"]

        if monthly.settlements.filter(month=month).exists():
            raise serializers.ValidationError(
                {"month": "Esta mensalidade já foi quitada neste mês."}
            )

        due_date = monthly.due_date_for(month)
        if due_date is None:
            raise serializers.ValidationError({"month": "Não há vencimento neste mês."})

        amount = data.get("amount", monthly.amount)
        if monthly.is_invoice:
            amount = monthly.invoice_items.filter(invoice_month=month).aggregate(
                total=Sum("amount")
            )["total"]
            if not amount:
                raise serializers.ValidationError({"amount": "A fatura deste mês está sem gastos."})
            if amount > Decimal("9999999999.99"):
                raise serializers.ValidationError(
                    {"amount": "O total da fatura está fora do limite."}
                )
            if "amount" in data and data["amount"] != amount:
                raise serializers.ValidationError({"amount": "Informe o valor total da fatura."})

        if monthly.invoice_id:
            invoice = Monthly.objects.select_for_update().get(pk=monthly.invoice_id)
            validate_open_invoice(invoice, month)

        settlement = monthly.settlements.create(
            month=month,
            due_date=due_date,
            type=monthly.type,
            amount=amount,
            settled_on=data["settled_on"],
        )
        Transaction.objects.create(
            user=monthly.user,
            type=settlement.type,
            amount=settlement.amount,
            bank=data["bank"],
            category="Fatura" if monthly.is_invoice else "Mensalidade",
            description=monthly.name,
            occurred_at=timezone.make_aware(datetime.combine(settlement.settled_on, time.min)),
            invoice_id=monthly.invoice_id,
            invoice_month=month if monthly.invoice_id else None,
            monthly_settlement=settlement if monthly.invoice_id or monthly.is_invoice else None,
        )
        return Response(
            MonthlySettlementSerializer(settlement).data, status=status.HTTP_201_CREATED
        )
