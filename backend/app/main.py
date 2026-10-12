import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import SessionLocal
from .mail import poll_forever
from .routes import (
    router,
    subjects_router,
    platforms_router,
    categories_router,
    backup_router,
    mail_router,
)

# /docs is a live console and the app has no auth, so it's off in production.
IS_PRODUCTION = os.getenv("ARTRACKER_ENV") == "production"

@asynccontextmanager
async def lifespan(_: FastAPI):
    poller = asyncio.create_task(poll_forever(SessionLocal))
    try:
        yield
    finally:
        poller.cancel()
        try:
            await poller
        except asyncio.CancelledError:
            pass


app = FastAPI(
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)
app.include_router(router)
app.include_router(subjects_router)
app.include_router(platforms_router)
app.include_router(categories_router)
app.include_router(backup_router)
app.include_router(mail_router)

# Mounted last so it doesn't shadow /api. No SPA fallback: unknown paths 404.
_default_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", _default_dist))

if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
