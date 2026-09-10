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

# /docs is not just a spec — it's a live console that can delete every tracker
# from a web form. The app has no auth of its own, so if the reverse proxy in
# front is ever misconfigured, an exposed /docs hands over the whole database.
# Off in production; still available locally where it's genuinely useful.
IS_PRODUCTION = os.getenv("ARTRACKER_ENV") == "production"

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Runs the mail poller alongside the app.

    In-process rather than a host cron job because the interval is a setting on
    the Settings page, and a value in the database can't reconfigure crontab. It
    also keeps the whole feature inside the one container the deployment already
    has.

    The task does nothing until the schedule is switched on, so this is inert on
    a fresh install. Tests never reach it: TestClient only runs lifespan inside a
    `with` block, and conftest doesn't use one.
    """
    poller = asyncio.create_task(poll_forever(SessionLocal))
    try:
        yield
    finally:
        # Cancelled and awaited, not just abandoned: without this the task can
        # still be mid-poll while the interpreter tears down, which surfaces as
        # noise on every shutdown and a half-finished pass.
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

# In production the React app is built to static files and served by this same
# process, so there's one origin and no CORS/proxy. In development we skip this
# entirely — Vite serves the frontend on :5173 and proxies /api here.
#
# Mounted LAST so it never shadows the /api routes above. html=True serves
# index.html for "/" — note it does NOT fall back to index.html for arbitrary
# unknown paths (those 404). Fine today: the app is a single view with no
# client-side router. If react-router is ever added, deep links will need an
# explicit catch-all route returning index.html.
_default_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", _default_dist))

if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
