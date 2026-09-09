FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS build
WORKDIR /build
COPY backend/ backend/
COPY nexus-contracts/ nexus-contracts/
RUN pip install --no-cache-dir --prefix=/install --constraint backend/constraints.txt ./backend

FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
COPY --from=build /install /usr/local
RUN useradd --uid 10001 --create-home nexus && mkdir /data && chown nexus:nexus /data
USER nexus
WORKDIR /home/nexus
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NEXUS_DB_PATH=/data/nexus.sqlite3 NEXUS_ENABLE_LIVE_MODEL=false
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "nexus_backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
