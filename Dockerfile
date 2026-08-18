FROM python:3.8.10-slim

WORKDIR /srv/backend

RUN pip install --no-cache-dir --upgrade "pip<25" \
    && useradd --uid 1001 --gid 0 --no-create-home \
        --home-dir /srv/backend --shell /usr/sbin/nologin app

COPY backend/pyproject.toml ./
COPY backend/app ./app

RUN pip install --no-cache-dir . \
    && mkdir -p /data /srv/backend/logs \
    && chgrp -R 0 /data /srv/backend/logs \
    && chmod -R g=u /data /srv/backend/logs

# OpenShift may replace this UID with an arbitrary non-root UID. Writable
# paths are group-0 writable, which supports both OpenShift and plain Docker.
USER 1001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AISUMMRY_RUNTIME_SETTINGS_FILE=/data/runtime-settings.json

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
