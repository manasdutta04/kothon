FROM node:22-alpine AS frontend-build
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
COPY config/ ./config/
RUN pip install --no-cache-dir uv && uv sync --extra audio
COPY --from=frontend-build /web/dist ./frontend/dist
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "kothon.api:app", "--host", "0.0.0.0", "--port", "8000"]
