import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import NotFound

from core.exceptions import RendvestAPIException


class MarketDataUnavailable(RendvestAPIException):
    error_code = "RENDVEST_ERROR_0012"
    status_code = 503
    default_detail = "Os dados de mercado estão temporariamente indisponíveis."


def get_market_data(path, timeout=None, *, quote=False):
    cache_key = f"investments:bolsai:{path}"
    if timeout is not None:
        data = cache.get(cache_key)
        if data is not None:
            return data

    if not settings.BOLSAI_API_KEY:
        raise MarketDataUnavailable()

    request = Request(
        f"https://api.usebolsai.com/api/v1/{path}",
        headers={"Accept": "application/json", "User-Agent": "Rendvest/1.0"},
    )
    request.add_unredirected_header("X-API-Key", settings.BOLSAI_API_KEY)
    try:
        with build_opener().open(request, timeout=5) as response:
            data = json.load(response)
    except HTTPError as error:
        error.close()
        if quote and error.code == 404:
            raise NotFound() from None
        raise MarketDataUnavailable() from None
    except (URLError, OSError, HTTPException, ValueError):
        raise MarketDataUnavailable() from None

    if not isinstance(data, dict):
        raise MarketDataUnavailable()
    if timeout is not None:
        cache.set(cache_key, data, timeout)
    return data
