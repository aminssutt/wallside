FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5002 \
    FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY manuel/ /app/manuel/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend

EXPOSE 5002

CMD ["sh", "-c", "gunicorn api:app --bind 0.0.0.0:${PORT:-5002} --workers 2 --threads 2 --timeout 120"]
