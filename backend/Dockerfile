FROM python:3.8.10-slim

WORKDIR /srv/backend

RUN pip install --no-cache-dir --upgrade "pip<25" \
    && groupadd --system app \
    && useradd --system --gid app --home /srv/backend app

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests
COPY data ./data

RUN pip install --no-cache-dir -e ".[dev]" \
    && mkdir -p /srv/backend/logs \
    && chown -R app:app /srv/backend

USER app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
