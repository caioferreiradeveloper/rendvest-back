import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework.exceptions import NotFound

from .bolsai import MarketDataUnavailable


def fetch_brapi(path):
    if not settings.BRAPI_API_TOKEN:
        raise MarketDataUnavailable()
    request = Request(
        f"https://brapi.dev/api/{path}",
        headers={"Accept": "application/json", "User-Agent": "Rendvest/1.0"},
    )
    request.add_unredirected_header("Authorization", f"Bearer {settings.BRAPI_API_TOKEN}")
    try:
        with urlopen(request, timeout=5) as response:
            data = json.load(response)
    except HTTPError as error:
        error.close()
        if error.code == 404:
            raise NotFound() from None
        raise MarketDataUnavailable() from None
    except (URLError, OSError, HTTPException, ValueError):
        raise MarketDataUnavailable() from None
    if not isinstance(data, dict) or data.get("error"):
        raise MarketDataUnavailable()
    return data
