import os
from fastapi import FastAPI, Response, Query, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from core.error_handlers import register_error_handlers
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
from model.database import engine, Base
from datetime import datetime, timezone
from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi.responses import JSONResponse


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
# Create all database tables
Base.metadata.create_all(bind=engine)

# Register exception handlers
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429,
    content={"success": False, "error": "Too many requests, please slow down."},
))


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
    Path("cache").mkdir(exist_ok=True)

    # Now data.countries are ORM objects, not dicts
    top_5 = sorted(data.countries, key=lambda c: c.estimated_gdp or 0, reverse=True)[:5]

    img = Image.new("RGB", (600, 300), color="white")
    draw = ImageDraw.Draw(img)

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
        draw.text((40, y), f"{country.name}", fill="black", font=font)
        y += 25

    y += 20
    draw.text((20, y), f"Last refreshed: {data.last_refreshed_at}", fill="black", font=font)
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
async def get_all_countries(
        request: Request,
        db: Session = Depends(get_db),
        currency: Optional[str] = Query(None, description="sort by currency"),
        sort: Optional[str] = Query(None, description="sort by GDP"),
        region: Optional[str] = Query(None, description="search for countries in a specific region"),
):
    query = db.query(Country)

    if currency:
        query = query.filter(Country.currency_code.ilike(f"%{currency}%"))
    if region:
        query = query.filter(Country.region.ilike(f"%{region}%"))

    countries = query.all()
    if not countries:
        raise NotFoundException("Country not found")

    # Sorting
    if sort == "gbd_desc":
        countries = sorted(countries, key=lambda c: c.estimated_gdp or 0, reverse=True)
    elif sort == "gdb_incr":
        countries = sorted(countries, key=lambda c: c.estimated_gdp or 0, reverse=False)

    result = [
        {
            "id": c.id,
            "name": c.name,
            "capital": c.capital,
            "region": c.region,
            "population": c.population,
            "currency_code": c.currency_code,
            "exchange_rate": c.exchange_rate,
            "estimated_gdp": c.estimated_gdp,
            "flag_url": c.flag_url,
            "last_refreshed_at": c.last_refreshed_at.isoformat()
        }
        for c in countries
    ]
    return JSONResponse(content=result, status_code=200, media_type="application/json")


@limiter.limit("8/minute")
@app.delete("/countries/clear")
async def clear_countries(request: Request):
    """Completely clear all country data and reset cache."""
    db: Session = SessionLocal()

    try:
        # Delete all countries
        deleted_count = db.query(Country).delete()

        # Reset the main DB instance timestamp
        country_db = db.query(CountryDBInstance).first()
        if country_db:
            country_db.last_refreshed_at = datetime.now(timezone.utc)

        db.commit()

        # Remove summary image if it exists
        image_path = os.path.join("cache", "summary.png")
        if os.path.exists(image_path):
            os.remove(image_path)

        return JSONResponse(
            content={
                "status": "success",
                "message": f"Database cleared successfully. {deleted_count} countries removed.",
                "last_refreshed_at": country_db.last_refreshed_at.isoformat() if country_db else None,
            },
            status_code=200,
        )

    finally:
        db.close()


@limiter.limit("8/minute")
@app.get("/countries/image")
async def get_image(request: Request):
    image_path = "cache/summary.png"
    if not os.path.exists(image_path):
        return NotFoundException("Summary image not found")
    return FileResponse(image_path, media_type="image/png")


@limiter.limit("8/minute")
@app.post("/countries/refresh")
async def fetch_countries(request: Request):
    """Fetch latest countries and update or insert them into the database."""

    countries_data = await fetch_all_countries(settings=get_settings())
    response = await extract_rate(data=countries_data, settings=get_settings())

    if not response:
        raise ExternalServiceUnavailable("timeout, try again later.")

    # Open database session
    db: Session = SessionLocal()

    try:
        # Get or create main DB instance
        country_db = db.query(CountryDBInstance).first()
        if not country_db:
            country_db = CountryDBInstance()
            db.add(country_db)
            db.commit()
            db.refresh(country_db)

        for item in response:
            # Match by name (case-insensitive)
            existing_country = (
                db.query(Country)
                .filter(func.lower(Country.name) == item["name"].lower())
                .first()
            )

            # # Generate random multiplier and recompute estimated GDP
            # multiplier = random.randint(1000, 2000)
            # population = item.get("population", 0)
            # exchange_rate = item.get("exchange_rate") or 1.0
            # estimated_gdp = population * exchange_rate * multiplier

            if existing_country:
                existing_country.capital = item.get("capital")
                existing_country.region = item.get("region")
                existing_country.population = item.get("population")
                existing_country.currency_code = item.get("currency_code")
                existing_country.exchange_rate = item.get("exchange_rate")
                existing_country.estimated_gdp = item.get("estimated_gdp")
                existing_country.flag_url = item.get("flag_url")
                existing_country.last_refreshed_at = datetime.now(timezone.utc)
            else:
                # INSERT new record
                new_country = Country(
                    name=item.get("name"),
                    capital=item.get("capital"),
                    region=item.get("region"),
                    population=item.get("population"),
                    currency_code=item.get("currency_code"),
                    exchange_rate=item.get("exchange_rate"),
                    estimated_gdp=item.get("estimated_gdp"),
                    flag_url=item.get("flag_url"),
                    last_refreshed_at=datetime.now(timezone.utc),
                    db_id=country_db.id,
                )
                db.add(new_country)

        # Update main database last refresh timestamp
        country_db.last_refreshed_at = datetime.now(timezone.utc)
        db.commit()

        # Generate image summary
        all_countries = db.query(Country).all()
        summary_data = {
            "countries": [c.__dict__ for c in all_countries],
            "last_refreshed_at": country_db.last_refreshed_at.isoformat(),
        }

        await create_image(CountryDB(**summary_data))

        return JSONResponse(
            content=response,
            status_code=201,
        )

    finally:
        db.close()


@limiter.limit("8/minute")
@app.get("/countries/{country_name}")
async def get_country(request: Request, country_name: str, db: Session = Depends(get_db)):
    if not country_name:
        raise BadRequestException("Country name can't be empty.")

    country = db.query(Country).filter(Country.name.ilike(country_name)).first()

    if not country:
        raise NotFoundException("Country not found")

    return JSONResponse(content={
        "id": country.id,
        "name": country.name,
        "capital": country.capital,
        "region": country.region,
        "population": country.population,
        "currency_code": country.currency_code,
        "exchange_rate": country.exchange_rate,
        "estimated_gdp": country.estimated_gdp,
        "flag_url": country.flag_url,
        "last_refreshed_at": country.last_refreshed_at.isoformat()
    }, status_code=200, media_type="application/json")


@limiter.limit("8/minute")
@app.delete("/countries/{country_name}")
async def remove_country(request: Request, country_name: str, db: Session = Depends(get_db)):
    if not country_name:
        raise BadRequestException("Country name can't be empty.")

    country = db.query(Country).filter(Country.name.ilike(country_name)).first()

    if not country:
        raise NotFoundException("Country not found")

    db.delete(country)
    db.commit()

    return JSONResponse(content={"message": f"{country_name} removed successfully"}, status_code=200)


@limiter.limit("8/minute")
@app.get("/status")
async def get_status(request: Request, db: Session = Depends(get_db)):
    count = db.query(Country).count()

    if count == 0:
        raise NotFoundException("No countries exist in db.")

    last_refresh = (
        db.query(CountryDBInstance)
        .order_by(CountryDBInstance.last_refreshed_at.desc())
        .first()
    )

    return JSONResponse(content={
        "total_countries": count,
        "last_refreshed_at": last_refresh.last_refreshed_at.isoformat() if last_refresh else None
    }, status_code=200, media_type="application/json")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)
