from pydantic import BaseModel
from typing import List
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone
from .database import Base


class Currency(BaseModel):
    code: str
    name: str
    symbol: str


class CountryItem(BaseModel):
    name: str
    capital: str | None = None
    region: str | None = None
    population: int
    currencies: Currency
    flag: str | None = None
    last_refreshed_at: str

class Countries(BaseModel):
    name: str
    capital: str | None = None
    region: str | None = None
    population: int
    currency_code: str | None = None
    exchange_rate: float | None = None
    estimated_gdp: float | None = None
    flag_url: str | None = None
    last_refreshed_at: datetime

    class Config:
        orm_mode = True


class CountryDB(BaseModel):
    countries: List[Countries]
    last_refreshed_at: datetime = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    class Config:
        orm_mode = True

class CountryDBInstance(Base):
    __tablename__ = "country_db"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_refreshed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # relationship to countries table
    countries = relationship("Country", back_populates="db", cascade="all, delete")


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    capital = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    population = Column(Integer, nullable=False)
    currency_code = Column(String(50), nullable=True)
    exchange_rate = Column(Float, nullable=True)
    estimated_gdp = Column(Float, nullable=True)
    flag_url = Column(String(255), nullable=True)
    last_refreshed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # foreign key reference to CountryDB
    db_id = Column(Integer, ForeignKey("country_db.id"))
    db = relationship("CountryDBInstance", back_populates="countries")
