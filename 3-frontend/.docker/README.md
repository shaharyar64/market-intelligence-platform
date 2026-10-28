# Docker Setup

From repo root:

```bash
docker compose -f .docker/docker-compose.yml up --build
```

Run in detached mode:

```bash
docker compose -f .docker/docker-compose.yml up --build -d
```

Stop service:

```bash
docker compose -f .docker/docker-compose.yml down
```

Build and push ARM64 image (for Graviton/ECR):

```bash
docker buildx build --platform linux/arm64 -f .docker/Dockerfile -t <image>:<tag> --push .
```

Deploy compose with explicit ARM64 platform when needed:

```bash
DOCKER_PLATFORM=linux/arm64 docker compose -f .docker/docker-compose.yml up -d --no-build
```
