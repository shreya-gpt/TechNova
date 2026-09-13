"""
Application entrypoint.

Run with:
    uvicorn app.main:app --reload

or via Docker (see Dockerfile / docker-compose.yml).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.database.repository import init_db

settings = get_settings()

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("main")

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Weather & Environmental Data module for the AI-powered Landslide Risk "
        "Intelligence and Early Warning Platform (North Eastern Region of India). "
        "Serves environmental observations, derived features and data-quality "
        "metadata to the downstream AI / Risk Engine. Does NOT produce a "
        "landslide probability itself."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def on_startup():
    init_db()
    logger.info("Weather & Environmental Data Module started. DEMO_MODE=%s", settings.DEMO_MODE)


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "status": "running",
        "demo_mode": settings.DEMO_MODE,
        "docs": "/docs",
        "primary_endpoint": "/environment/risk-features",
    }
