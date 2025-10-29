from fastapi import Depends
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from model.index import CountryItem
from services.http_client import safe_http_request
from functools import lru_cache
from typing_extensions import Annotated
from core import config
from typing import List


@lru_cache
def get_settings():
    return config.Settings()


async def fetch_all_countries(settings: Annotated[config.Settings, Depends(get_settings)]):
    url = settings.countries_api_url
    countries = await safe_http_request("GET", url, timeout=3000)

    if not countries:
        return JSONResponse(content={
            {
                "error": "External data source unavailable",
                "details": "Could not fetch data from Country Api"
            }
        }, status_code=503, media_type="application/json")

    data: List[CountryItem] = []
    for country in countries:
        data.append(
            CountryItem(name=country.get('name'), capital=country.get('capital'),
                        region=country.get('region'),
                        population=country.get('population'), flag=country.get('flag'),
                        currencies=country.get('currencies')[0] if country.get('currencies') else country.get(
                            'currencies', {"code": "", "name": "", "symbol": ""}),
                        last_refreshed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")))

    return data
