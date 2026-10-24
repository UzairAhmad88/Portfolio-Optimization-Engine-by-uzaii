from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.routes import router as v1_router
from app.db.session import init_db

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate production security configuration (fails closed if insecure in production)
    from app.auth.security import validate_jwt_configuration
    validate_jwt_configuration()

    # Initialize database tables on application startup
    try:
        init_db()
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.warning("Database schema initialization encountered an error: %s", exc)
    yield


app = FastAPI(
    title="Quant Portfolio Engine API",
    description=(
        "Production-grade Quantitative Portfolio Research and Optimization Engine. "
        "Provides market data ingestion, persistent database storage, portfolio validation, "
        "constrained mean-variance optimization, efficient-frontier generation, and comparative risk analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Explicit trusted origins for CORS; wildcard origins are strictly prohibited with credentialed requests
raw_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip() and o.strip() != "*"]
if not allowed_origins:
    allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Appends standard defensive HTTP security headers to all API responses.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    logger.exception("Unhandled server exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred."},
    )


app.include_router(v1_router, prefix="/api/v1")
