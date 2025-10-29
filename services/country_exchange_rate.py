from random import randint
from fastapi import Depends
from fastapi.responses import JSONResponse
from model.index import CountryItem
from services.http_client import safe_http_request
from functools import lru_cache
from typing_extensions import Annotated
from core import config
from pydantic import BaseModel
from typing import Dict, List


@lru_cache
def get_settings():
    return config.Settings()


class Rate(BaseModel):
    result: str
    rates: Dict[str, int]


async def extract_rate(data: List[CountryItem], settings: Annotated[config.Settings, Depends(get_settings)]):
    url = settings.exchange_rate_url
    response: Rate = await safe_http_request("GET", url, timeout=3000)

    if response['result'] != "success":
        return JSONResponse(content={
            {
                "error": "External data source unavailable",
                "details": "Could not fetch data from Exchange Rate Api"
            }
        }, status_code=503, media_type="application/json")

    complete_data_db = []

    for item in data:
        currency_code = item.currencies.code if item.currencies.code != "" else None
        exchange_rate = response['rates'].get(currency_code, None) if currency_code else None
        estimated_gdp = (item.population * randint(1000,
                                                   2000) * exchange_rate) if item.currencies.code != "" and exchange_rate else (
            0 if item.currencies.symbol == "" else None)

        complete_data_db.append({
            "name": item.name,
            "capital": item.capital,
            "region": item.region,
            "population": item.population,
            "currency_code": currency_code,
            "exchange_rate": exchange_rate,
            "estimated_gdp": estimated_gdp,
            "flag_url": item.flag,
            "last_refreshed_at": item.last_refreshed_at,
        })

    return complete_data_db
