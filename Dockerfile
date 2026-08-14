# ---- Stage 1: build the React app ----------------------------------------
# Node is only needed to produce frontend/dist. None of it ships in the final
# image — that's the point of the multi-stage build.
FROM node:22-alpine AS frontend

WORKDIR /build

# Copy manifests first so this layer is cached until dependencies actually
# change; editing a component then skips the whole npm install step.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---- Stage 2: the runtime image ------------------------------------------
FROM python:3.12-slim AS runtime

# Don't write .pyc files, and keep stdout unbuffered so container logs appear
# immediately instead of being held in a buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

# Only the built assets come across from stage 1 — no node_modules, no sources.
COPY --from=frontend /build/dist ./frontend_dist

# Where main.py looks for the built frontend, and where the SQLite file lives.
# /data is a mount point so the database survives container rebuilds.
ENV FRONTEND_DIST=/app/frontend_dist \
    DATABASE_URL=sqlite:////data/artracker.db

RUN mkdir -p /data

EXPOSE 8000

# 0.0.0.0 (not 127.0.0.1) or the port publish won't reach the app from outside.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
