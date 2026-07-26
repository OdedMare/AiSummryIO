FROM python:3.8.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/backend

# Some pinned dependencies have no prebuilt wheel for every platform (notably
# backports.zoneinfo on arm64, pulled in by pydantic on Python 3.8), so the
# image needs a compiler at install time. It is removed again below to keep the
# runtime image slim.
# python:3.8.10-slim is Debian 10 (buster), which is EOL: deb.debian.org no
# longer serves it and apt-get update 404s. Point apt at the archive instead.
RUN printf '%s\n' \
        'deb http://archive.debian.org/debian buster main' \
        'deb http://archive.debian.org/debian-security buster/updates main' \
        > /etc/apt/sources.list \
    && printf 'Acquire::Check-Valid-Until "false";\n' \
        > /etc/apt/apt.conf.d/99no-check-valid-until \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

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
    && rm -rf wheelhouse \
    && apt-get purge -y gcc python3-dev \
    && apt-get autoremove -y

RUN useradd --create-home app \
    && mkdir -p /data /srv/backend/logs \
    && chown -R app:app /data /srv/backend
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
