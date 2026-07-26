# wheelhouse — internal `flunks` wheel

`flunks` is the internal FLAPI Flow Package runtime. It is **not on PyPI**, so
`pip install .` cannot resolve it from a normal machine and the backend image
cannot build without one of the two sources below.

Wheels here are deliberately **not committed** (see `.gitignore`). Only this
README and the pin file are tracked.

## Option 1 — local wheelhouse (air-gapped builds)

Download the wheel on a machine that can reach the internal index, then drop it
in this directory:

```bash
pip download flunks==<version> \
  --index-url https://<internal-index>/simple \
  --dest backend/wheelhouse/
```

`docker build` picks it up automatically via `--find-links`.

## Option 2 — internal index at build time

```bash
docker build ./backend \
  --build-arg PIP_INDEX_URL=https://<internal-index>/simple \
  --build-arg PIP_TRUSTED_HOST=<internal-index-host>
```

## Pinning

`pyproject.toml` currently requires bare `flunks` with no version. Once the
exact tested version is known, pin it there and record the version and sha256
in `PINNED.md` so a rebuild is reproducible. P0 requires this pin before
release.

Verify a downloaded wheel's checksum with:

```bash
shasum -a 256 backend/wheelhouse/flunks-*.whl
```

## Verification

The image build runs `import flunks` immediately after install, so a missing or
broken wheel fails the build instead of surfacing on the first package call.
That is exactly how the `FlapiConfig` / `FlApiConfig` typo reached `main`.
