# Django imports
from django.db import transaction
from django_filters import rest_framework as filters
from rest_framework import generics, status
from rest_framework.response import Response

# App imports
from apps.debtors.models import Debtor
from apps.debtors.serializers import DebtorPaymentSerializer, DebtorSerializer
from apps.transactions.models import Transaction
from core.enums import Type


# Filter responsible for filtering debtors by person name and dates
class DebtorFilter(filters.FilterSet):
    class Meta:
        model = Debtor
        fields = ["debtor_name", "occurred_at", "paid_at"]


# Mixin responsible for restricting debtor queries to the authenticated user
class DebtorQuerysetMixin:
    def get_queryset(self):
        return Debtor.objects.filter(user=self.request.user)


# API view responsible for listing the authenticated user's debtors
class DebtorList(DebtorQuerysetMixin, generics.ListAPIView):
    serializer_class = DebtorSerializer
    filterset_class = DebtorFilter
    ordering_fields = ["occurred_at", "amount", "paid_at", "created_at"]
    ordering = ["-occurred_at", "-created_at"]


# API view responsible for creating new debtors
class DebtorCreate(generics.CreateAPIView):
    serializer_class = DebtorSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# API view responsible for retrieving a specific debtor
class DebtorDetail(DebtorQuerysetMixin, generics.RetrieveAPIView):
    serializer_class = DebtorSerializer


# API view responsible for updating an existing debtor
class DebtorUpdate(DebtorQuerysetMixin, generics.UpdateAPIView):
    serializer_class = DebtorSerializer

    def get_queryset(self):
        return super().get_queryset().select_for_update()

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)


# API view responsible for deleting an existing debtor
class DebtorDelete(DebtorQuerysetMixin, generics.DestroyAPIView):
    serializer_class = DebtorSerializer


# API view responsible for marking a debtor as paid
class DebtorPay(DebtorQuerysetMixin, generics.GenericAPIView):
    serializer_class = DebtorPaymentSerializer

    def get_queryset(self):
        return super().get_queryset().select_for_update()

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        debtor = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={"debtor": debtor},
        )
        serializer.is_valid(raise_exception=True)
        debtor = serializer.save()
        Transaction.objects.create(
            user=debtor.user,
            type=Type.INCOME,
            amount=debtor.paid_amount,
            bank=serializer.validated_data["bank"],
            category="Recebimento de devedor",
            description=debtor.debtor_name,
            occurred_at=debtor.paid_at,
        )
        return Response(DebtorSerializer(debtor).data, status=status.HTTP_200_OK)
