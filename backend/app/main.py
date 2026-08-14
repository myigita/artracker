import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router, subjects_router, platforms_router

app = FastAPI()
app.include_router(router)
app.include_router(subjects_router)
app.include_router(platforms_router)

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
