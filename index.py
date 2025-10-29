import os
from fastapi import FastAPI, Request, Response, Query, Depends
from fastapi.responses import FileResponse
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from core.error_handlers import register_error_handlers, conditional_validation_handler
from model.index import CountryDB, CountryDBInstance, Country
from model.database import SessionLocal
from services.country_data import fetch_all_countries
from services.country_exchange_rate import extract_rate
from core.exceptions import NotFoundException, BadRequestException, ExternalServiceUnavailable
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from functools import lru_cache
from core import config
from contextlib import asynccontextmanager
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from sqlalchemy.orm import Session



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("App starting up...")
    await startup_event()
    yield
    # Shutdown
    print("App shutting down...")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(lifespan=lifespan, title="My Profile App")
register_error_handlers(app)

# Register exception handlers
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429,
    content={"success": False, "error": "Too many requests, please slow down."},
))
app.add_exception_handler(RequestValidationError, conditional_validation_handler)


@lru_cache
def get_settings():
    return config.Settings()


# Initialize the limiter
async def startup_event():
    app.state.limiter = limiter


origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# db = CountryDB(
#     countries=[],
#     last_refreshed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
# )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_instance = CountryDBInstance(
    last_refreshed_at=datetime.now(timezone.utc)
)


async def create_image(data):
    # Ensure cache directory exists
    Path("cache").mkdir(exist_ok=True)

    top_5 = sorted(data.countries, key=lambda c: c['estimated_gdp'] or 0, reverse=True)[:5]

    # 🧠 Step 3: Create a summary image
    img = Image.new("RGB", (600, 300), color="white")
    draw = ImageDraw.Draw(img)

    # You can customize font
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()

    y = 20
    draw.text((20, y), f" Country Summary Report", fill="black", font=font)
    y += 40
    draw.text((20, y), f"Total countries: {len(data.countries)}", fill="black", font=font)
    y += 30

    draw.text((20, y), "Top 5 by GDP:", fill="black", font=font)
    y += 30
    for country in top_5:
        draw.text(
            (40, y),
            f"{country['name']}",
            fill="black",
            font=font,
        )
        y += 25

    y += 20
    draw.text((20, y), f"Last refreshed: {data.last_refreshed_at}", fill="black", font=font)

    # Step 4: Save it
    img.save("cache/summary.png")


@app.get("/")
async def home():
    return JSONResponse(content={
        "success": True,
        "message": "welcome to my profile api"
    }, status_code=200, media_type="application/json")


@app.get("/health")
async def health_check():
    return JSONResponse(content={
        "success": True,
        "message": "Ok"
    }, status_code=200, media_type="application/json")


@limiter.limit("8/minutes")
@app.get("/countries")
async def get_all_countries(request: Request, currency: Optional[str] = Query(None, description="sort by currency"),
                            sort: Optional[str] = Query(None, description="sort by gdp"),
                            region: Optional[str] = Query(None,
                                                          description="search for countries in a specific region"), ):
    curr = currency.lower() if currency else ""
    sort = sort.lower() if sort else ""
    region = region.lower() if region else ""

    countries = []

    for country in db.countries:
        if curr and region:
            if country.get('currency_code') and country.get('currency_code').lower() == curr:
                if country.get('region') and country.get('region').lower() == region:
                    countries.append(country)
        elif curr and not region:
            if country.get('currency_code') and country.get('currency_code').lower() == curr:
                countries.append(country)
        elif curr == "" and region:
            if country.get('region') and country.get('region').lower() == region:
                countries.append(country)
        else:
            countries.append(country)

    sorted_countries = []
    if countries:
        if sort and sort == "gbd_desc":
            countries = sorted(countries, key=lambda country: country.estimated_gdp or 0, reverse=True)
            sorted_countries.append(countries)
        elif sort and sort == "gdb_incr":
            countries = sorted(countries, key=lambda country: country.estimated_gdp or 0, reverse=False)
            sorted_countries.append(countries)
        else:
            sorted_countries = countries
    else:
        raise NotFoundException("Country not found")

    return JSONResponse(content=sorted_countries, status_code=200, media_type="application/json")


@limiter.limit("8/minute")
@app.get("/countries/image")
async def get_image(request: Request):
    image_path = "cache/summary.png"
    if not os.path.exists(image_path):
        return NotFoundException("Summary image not found")
    return FileResponse(image_path, media_type="image/png")


@limiter.limit("8/minute")
@app.post("/countries/refresh")
async def fetch_countries(request: Request, db: Session = Depends(get_db)):
    countries_data = await fetch_all_countries(settings=get_settings())
    response = await extract_rate(data=countries_data, settings=get_settings())

    if not response:
        raise ExternalServiceUnavailable("timeout, try again later.")

    db_instance = CountryDBInstance(last_refreshed_at=datetime.now(timezone.utc))
    db.add(db_instance)
    db.commit()
    db.refresh(db_instance)

    for item in response:
        country = Country(
            name=item["name"],
            capital=item.get("capital"),
            region=item.get("region"),
            population=item["population"],
            currency_code=item.get("currency_code"),
            exchange_rate=item.get("exchange_rate"),
            estimated_gdp=item.get("estimated_gdp"),
            flag_url=item.get("flag_url"),
            last_refreshed_at=datetime.now(timezone.utc),
            db_id=db_instance.id
        )
        db.add(country)

    db.commit()

    db.countries = response
    await create_image(db)

    return JSONResponse(content=response, status_code=201, media_type="application/json")


@limiter.limit("8/minute")
@app.get("/countries/{country_name}")
async def get_country(request: Request, country_name: str):
    if not country_name:
        raise BadRequestException("Country name can't be empty.")

    name = country_name.lower() if country_name else ""
    fetched_country = []

    if name:
        for I in db.countries:
            if I.get('name').lower() == name:
                fetched_country.append(I)

    if not fetched_country:
        raise NotFoundException("Country not found")

    return JSONResponse(content=fetched_country[0], status_code=200, media_type="application/json")


@limiter.limit("8/minute")
@app.delete("/countries/{country_name}")
async def remove_country(request: Request, country_name: str):
    if not country_name:
        raise BadRequestException("Country name can't be empty.")

    name = country_name.lower() if country_name else ""

    if name:
        for I in db.countries:
            if I.get('name').lower() == name:
                db.countries.remove(I)
                return JSONResponse(content={}, status_code=200, media_type="application/json")

    raise NotFoundException("Country not found")


@limiter.limit("8/minute")
@app.get("/status")
async def get_status(request: Request):
    countries_count = len(db.countries)

    if not countries_count:
        raise NotFoundException("No countries exist in db.")

    return JSONResponse(content={
        "total_countries": countries_count,
        "last_refreshed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }, status_code=200, media_type="application/json")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)
