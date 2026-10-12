# Stage 1: build the React app
FROM node:22-alpine AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Stage 2: runtime
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

COPY --from=frontend /build/dist ./frontend_dist

# /data is a volume mount so the database survives rebuilds.
ENV FRONTEND_DIST=/app/frontend_dist \
    DATABASE_URL=sqlite:////data/artracker.db \
    ARTRACKER_ENV=production

RUN mkdir -p /data

EXPOSE 8000

# 0.0.0.0 (not 127.0.0.1) or the port publish won't reach the app from outside.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
