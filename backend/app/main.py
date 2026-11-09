# Configure the FastAPI application, lifecycle, routes, and sanitized errors.
import logging
import os
from contextlib import asynccontextmanager

from dotenv import dotenv_values
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.engine import make_url

from backend.app.config import get_settings
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.products import router as products_router
from backend.app.routers.intelligence import router as intelligence_router

from backend.app.routers.retrieval import router as retrieval_router
from backend.app.routers.chat import router as chat_router
from backend.app.routers.investigations import router as investigations_router

# Initialize application resources during startup and release them during shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = get_settings()
        valid_database = make_url(settings.database_url).get_backend_name() == "postgresql"
    except Exception:
        raise RuntimeError("Invalid backend configuration; check DATABASE_URL and environment settings.") from None
    if not valid_database:
        raise RuntimeError("DATABASE_URL must specify PostgreSQL")
    if not settings.groq_model.strip():
        raise RuntimeError("GROQ_MODEL must not be empty")
    yield


app = FastAPI(title="ZeroInsight AI", version="0.1.0", lifespan=lifespan)


# Return validation errors without exposing submitted customer content.
@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request parameters."})


# Log a reference for unexpected errors while returning a sanitized response.
@app.middleware("http")
async def internal_error(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logging.getLogger(__name__).error("Unhandled request failure; type=%s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in (os.getenv("FRONTEND_ORIGINS") or dotenv_values(".env").get("FRONTEND_ORIGINS") or "http://127.0.0.1:5173,http://localhost:5173").split(",") if origin.strip() and origin.strip() != "*"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(products_router)
app.include_router(intelligence_router)
app.include_router(retrieval_router)
app.include_router(chat_router)
app.include_router(investigations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
