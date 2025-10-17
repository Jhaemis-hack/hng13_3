from fastapi import FastAPI, Request, Response, Depends
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from core.error_handlers import register_error_handlers
from services.http_client import safe_http_request
from core.exceptions import NotFoundException
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from functools import lru_cache
from typing_extensions import Annotated
from core import config
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("App starting up...")
    await startup_event()
    yield
    # Shutdown
    print("App shutting down...")


app = FastAPI(lifespan=lifespan, title="My Profile App")
register_error_handlers(app)


@lru_cache
def get_settings():
    return config.Settings()


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"success": False, "error": "Too many requests, please slow down."},
    )


# Initialize the limiter
limiter = Limiter(key_func=get_remote_address)


async def startup_event():
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


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

Profile_details = {
    "email": "gbemilekekenny@gmail.com",
    "name": "James Kehinde",
    "stack": "NodeJs",
}


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


@limiter.limit("8/minute")
@app.get("/me")
async def get_profile(request: Request, settings: Annotated[config.Settings, Depends(get_settings)]):
    url = settings.cat_api_url
    fact = await safe_http_request("GET", url, params={"max_length": 40}, timeout=3000)

    if not fact:
        raise NotFoundException("timeout, try again later.")

    data = {
        "status": "success",
        "user": Profile_details,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "fact": fact["fact"]
    }
    return JSONResponse(content=data, status_code=200, media_type="application/json")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)
