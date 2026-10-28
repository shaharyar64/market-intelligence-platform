# Docker Setup

From repo root:

```bash
docker compose -f .devops/docker-compose.yml up --build
```

Run in detached mode:

```bash
docker compose -f .devops/docker-compose.yml up --build -d
```

Stop services:

```bash
docker compose -f .devops/docker-compose.yml down
```

Exposed ports:

- `gateway`: `8000`
- `bankspatial`: `8001`
- `ev`: `8002`
- `horeca`: `8003`
- `beer`: `8004`
- `digital`: `8005`
- `scraping`: `8006`
- `real-estate`: `8007`
- `saudi-real-estate`: `8009`
- `bank-brand-health`: `8011`
- `uae-bank-brand-health`: `8013`

# ARM64 (AWS Graviton)

This compose file is pinned to `linux/arm64` for all services.

Run on Graviton EC2:

```bash
docker compose -f .devops/docker-compose.yml up --build -d
```

If you build images on x86 and push to ECR for Graviton, build ARM64 explicitly:

```bash
docker buildx build --platform linux/arm64 -f .devops/Dockerfile -t <image>:<tag> --push .
```

# Faster Builds

The repo now uses a root `.dockerignore` and Docker BuildKit cache mounts for pip.

If BuildKit is not enabled by default on your machine:

```bash
DOCKER_BUILDKIT=1 docker compose -f .devops/docker-compose.yml build
```

# Service-level deploys

Each image contains only `shared/` and its own service dir (`SERVICE_DIR` build arg in
the Dockerfile/compose). The prod workflow diffs the push and builds/pulls/redeploys only
affected services. Changes to `shared/`, `requirements-base.txt`, the Dockerfile or the
workflow rebuild everything; `requirements-food.txt` rebuilds food + trends-real-estate.
Force a deploy from the Actions tab with `services` = `all` or e.g. `ev,food`.
`shared/` and services must not import from `gateway/` (it isn't in their images).
