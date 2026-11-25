FROM ubuntu:24.04 AS web-build

ARG FLUTTER_VERSION=3.50.0
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    FLUTTER_SUPPRESS_ANALYTICS=true \
    PATH="/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git unzip xz-utils zip libglu1-mesa \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --depth 1 --branch "${FLUTTER_VERSION}" https://github.com/flutter/flutter.git /opt/flutter \
    && flutter config --no-analytics --enable-web \
    && flutter precache --web

WORKDIR /build/mobile
COPY mobile/pubspec.yaml mobile/pubspec.lock ./
RUN flutter pub get --enforce-lockfile

COPY mobile/lib ./lib
COPY mobile/assets ./assets
COPY mobile/web ./web
RUN flutter build web --release --no-pub --no-web-resources-cdn

FROM python:3.14-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TUSHUM_DATABASE=/data/tushum.sqlite3

WORKDIR /app
COPY backend/requirements-lock.txt ./backend/requirements-lock.txt
COPY backend/voice-requirements-lock.txt ./backend/voice-requirements-lock.txt
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r backend/requirements-lock.txt

COPY backend ./backend
COPY --from=web-build /build/mobile/build/web ./mobile/build/web
RUN mkdir -p /data

EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
