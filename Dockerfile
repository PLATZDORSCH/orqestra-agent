# ── Stage 1: Build web frontend ──────────────────────────────────────
FROM node:22-slim AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
# pyproject.toml is the single source of truth for the app version;
# vite.config.ts reads it at build time and bakes it into the bundle.
COPY pyproject.toml /pyproject.toml
COPY web/ .
RUN npm run build

# ── Stage 2: Python runtime ─────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# System libraries required by WeasyPrint (PDF export of wiki pages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Application code & packaging metadata
COPY pyproject.toml requirements.txt ./
COPY src/ src/
COPY ascii_logo.txt .

# Static assets shipped with the image (bootstrap content for first run)
COPY templates/ templates/
COPY personas/ personas/

RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install-deps chromium \
    && playwright install chromium \
    && python -c "import telegram; print('telegram-bot OK')"

# Default config — overridden at runtime by a compose volume mount
COPY config.yaml .

# Built web frontend
COPY --from=web-build /web/dist web/dist/

# NOTE: `departments/`, `knowledge_base/`, `skills/`, `data/` and the
# user-editable `*.yaml` files are intentionally NOT baked into the image.
# They are mounted from the host via compose.yaml so user data and any
# locally installed departments / wiki content survive container rebuilds.

ENTRYPOINT ["orqestra"]
