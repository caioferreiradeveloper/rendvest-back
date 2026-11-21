from .bolsai import MarketDataUnavailable
from .serializers import Quote
from .snapshots import get_market_snapshot


def get_quote(ticker):
    def format_quote(data):
        quote = Quote(
            data={
                "ticker": data.get("ticker"),
                "price": data.get("close"),
                "currency": "BRL",
                "trade_date": data.get("trade_date"),
            }
        )
        if not quote.is_valid():
            raise MarketDataUnavailable()
        return Quote(quote.validated_data).data

    return get_market_snapshot(f"stocks/{ticker}/quote", format_quote)
