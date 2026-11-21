from rest_framework import serializers

from core.enums import Bank


class DashboardParams(serializers.Serializer):
    bank = serializers.ChoiceField(choices=Bank.choices, required=False, default="")


class Money(serializers.DecimalField):
    def __init__(self):
        super().__init__(max_digits=24, decimal_places=2, coerce_to_string=True)


class TransactionMetrics(serializers.Serializer):
    balance = Money()
    income = Money()
    expenses = Money()
    net = Money()
    transaction_count = serializers.IntegerField()


class LoanMetrics(serializers.Serializer):
    active_count = serializers.IntegerField()
    outstanding = Money()
    paid_this_month = Money()
    overdue_installments = serializers.IntegerField()


class DebtorMetrics(serializers.Serializer):
    outstanding = Money()
    open_count = serializers.IntegerField()
    received_this_month = Money()


class WishlistMetrics(serializers.Serializer):
    count = serializers.IntegerField()
    total = Money()
    planned_this_month = Money()


class MonthlyMetrics(serializers.Serializer):
    settled_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    pending_income = Money()
    pending_expenses = Money()


class MonthlyFlow(serializers.Serializer):
    month = serializers.DateField()
    income = Money()
    expenses = Money()
    net = Money()


class RecentTransaction(serializers.Serializer):
    id = serializers.UUIDField()
    category = serializers.CharField()
    description = serializers.CharField()
    amount = Money()
    type = serializers.CharField()
    bank = serializers.CharField()
    occurred_at = serializers.DateTimeField()


class Dashboard(serializers.Serializer):
    as_of = serializers.DateField()
    transactions = TransactionMetrics()
    loans = LoanMetrics()
    debtors = DebtorMetrics()
    wishlist = WishlistMetrics()
    monthlies = MonthlyMetrics()
    history = MonthlyFlow(many=True)
    recent = RecentTransaction(many=True)
