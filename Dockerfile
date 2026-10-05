FROM node:24-bookworm-slim AS ui
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ARG APP_COMMIT=development
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home controldeck
COPY backend/ backend/
COPY VERSION LICENSE ./
RUN python -c "import json,pathlib; pathlib.Path('build-info.json').write_text(json.dumps({'version':pathlib.Path('VERSION').read_text().strip(),'commit':'${APP_COMMIT}'}))"
COPY --from=ui /build/out/ frontend/out/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready',timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--worker-tmp-dir", "/tmp", "backend.app:app"]
