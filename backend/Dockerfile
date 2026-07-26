FROM python:3.8.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/backend

# flunks is internal and not on the public index, so the build needs a source
# for it. Provide exactly one of:
#   1. a wheelhouse — put the wheel in backend/wheelhouse/ (see wheelhouse/README.md)
#   2. an internal index — build with
#      --build-arg PIP_INDEX_URL=https://<internal-index>/simple
# With neither, `pip install .` fails on flunks and the image cannot build.
ARG PIP_INDEX_URL=""
ARG PIP_EXTRA_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""

COPY pyproject.toml ./
COPY wheelhouse ./wheelhouse
COPY app ./app

RUN if [ -n "$(ls -A wheelhouse/*.whl 2>/dev/null)" ]; then \
        echo "Installing flunks from the local wheelhouse"; \
        pip install --no-cache-dir --find-links=./wheelhouse .; \
    else \
        echo "No wheelhouse content; using the configured index"; \
        pip install --no-cache-dir .; \
    fi \
    && python -c "import flunks; print('flunks OK:', getattr(flunks, '__version__', 'unknown'))" \
    && rm -rf wheelhouse

RUN useradd --create-home app \
    && mkdir -p /data /srv/backend/logs \
    && chown -R app:app /data /srv/backend
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
