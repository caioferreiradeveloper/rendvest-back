from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .catalog import list_funds
from .models import Investment


class AssetSearchParams(serializers.Serializer):
    type = serializers.ChoiceField(choices=("stock", "fii"))
    q = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    page = serializers.IntegerField(required=False, min_value=1, default=1)


class Asset(serializers.Serializer):
    ticker = serializers.CharField()
    name = serializers.CharField(allow_null=True)
    segment = serializers.CharField(allow_null=True)


class AssetSearchResult(serializers.Serializer):
    count = serializers.IntegerField()
    next_page = serializers.IntegerField(allow_null=True)
    results = Asset(many=True)


class TickerParams(serializers.Serializer):
    ticker = serializers.RegexField(r"\A[A-Za-z0-9]{4}[0-9]{1,2}\Z")


class Quote(serializers.Serializer):
    ticker = serializers.CharField()
    price = serializers.DecimalField(max_digits=20, decimal_places=4)
    currency = serializers.ChoiceField(choices=("BRL",))
    trade_date = serializers.DateField()


class InvestmentSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(choices=(Investment.Type.FII,), default=Investment.Type.FII)
    asset = serializers.RegexField(
        r"\A[A-Za-z0-9]{4}11\Z", error_messages={"invalid": "Informe o código de um FII."}
    )
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    quantity = serializers.IntegerField(min_value=1, max_value=2_147_483_647)

    class Meta:
        model = Investment
        fields = ("id", "type", "asset", "amount", "invested_at", "quantity")

    def validate_invested_at(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("A data da aplicação não pode ser futura.")
        return value

    def validate(self, attrs):
        ticker = attrs["asset"].upper()
        if not any(fund["ticker"] == ticker for fund in list_funds()):
            raise serializers.ValidationError({"asset": "FII não encontrado no catálogo."})
        attrs["asset"] = ticker
        return attrs
