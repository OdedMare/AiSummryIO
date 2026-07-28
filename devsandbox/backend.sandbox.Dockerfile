# Sandbox backend image: the real backend plus a MOCK `flunks`.
#
# The production Dockerfile runs `pip install -e ".[dev]"`, which resolves
# `flunks` from the internal index. That index is unreachable here, so the
# mock is installed FIRST — pip then sees the requirement as already
# satisfied and leaves it alone.
#
# Build context is the repository root, so both `backend/` and `devsandbox/`
# are visible.

FROM python:3.8.10-slim

WORKDIR /srv/backend

# `backports.zoneinfo` (a Python 3.8-only transitive dependency) ships no
# wheel for this platform and is compiled from source, so the sandbox image
# needs a toolchain the production image can do without.
#
# This base is Debian buster, which is end-of-life: its packages have moved
# to archive.debian.org and the mirrors baked into the image serve no Release
# file. Repointing apt at the archive is what makes the toolchain
# installable. Signatures are still verified against the keyring already in
# the image; only the "valid until" date is ignored, since the archive's
# Release file is deliberately frozen in the past.
RUN printf '%s\n' \
        'deb http://archive.debian.org/debian buster main' \
        > /etc/apt/sources.list \
    && apt-get update -o Acquire::Check-Valid-Until=false \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade "pip<25" \
    && groupadd --system app \
    && useradd --system --gid app --home /srv/backend app

# The mock must land before the backend install, so `flunks` resolves.
COPY devsandbox/fake_flunks /srv/fake_flunks
RUN pip install --no-cache-dir /srv/fake_flunks

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/tests ./tests
COPY backend/data ./data

RUN pip install --no-cache-dir -e ".[dev]" \
    && mkdir -p /srv/backend/logs \
    && chown -R app:app /srv/backend

USER app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
