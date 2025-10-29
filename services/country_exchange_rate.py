from fastapi import FastAPI, Request, Response, Depends
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from core.error_handlers import register_error_handlers
from core.error_handlers import register_error_handlers, conditional_validation_handler
from model.index import CountryItem
from services.http_client import safe_http_request
from core.exceptions import NotFoundException
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from functools import lru_cache
from typing_extensions import Annotated
from core import config
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


@lru_cache
def get_settings():
    return config.Settings()


async def fetch_all_countries(settings: Annotated[config.Settings, Depends(get_settings)]):
    url = settings.countries_api_url
    countries = await safe_http_request("GET", url, timeout=3000)

    if not countries:
        raise NotFoundException("timeout, try again later.")

    data: List[CountryItem] = []
    for country in countries:
        data.append(CountryItem(name=country.name, capital=country.capital, region=country.region,
                                population=country.population, flag=country.flag,
                                last_refreshed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), ))

    return data
