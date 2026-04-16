# ── Stage 1: Build web frontend ──────────────────────────────────────
FROM node:22-slim AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# ── Stage 2: Python runtime ─────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY src/ src/
COPY ascii_logo.txt .
COPY templates/ templates/
COPY personas/ personas/
COPY departments/ departments/
COPY config.yaml .

RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install-deps chromium \
    && playwright install chromium \
    && python -c "import telegram; print('telegram-bot OK')"

COPY knowledge_base/ knowledge_base/
COPY skills/ skills/

COPY --from=web-build /web/dist web/dist/

ENTRYPOINT ["orqestra"]
