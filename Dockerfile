FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY main.py .
COPY core/ core/
COPY capabilities/ capabilities/
COPY personas/ personas/
COPY config.yaml .

RUN pip install --no-cache-dir -e ".[analysis,browser]" \
    && playwright install-deps chromium \
    && playwright install chromium

COPY knowledge_base/ knowledge_base/
COPY skills/ skills/

ENTRYPOINT ["cod"]
