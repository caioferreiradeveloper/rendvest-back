from rest_framework import serializers


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
