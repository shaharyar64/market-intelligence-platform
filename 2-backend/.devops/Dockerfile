# syntax=docker/dockerfile:1.7

# ---- builder: compilers + pip live here only; nothing from this stage but /opt/venv ships
FROM python:3.11-slim AS builder

# Only services with deps that need a compiler (e.g. hdbscan for food) set this.
ARG INSTALL_BUILD_TOOLS=false
RUN if [ "$INSTALL_BUILD_TOOLS" = "true" ]; then \
      apt-get update && \
      apt-get install --no-install-recommends -y build-essential && \
      rm -rf /var/lib/apt/lists/*; \
    fi

# Optional service-specific extras file (e.g. requirements-food.txt), installed on top
# of requirements-base.txt. Single file on purpose: COPY splits its args before ARG
# expansion, so a space-separated list wouldn't work. Defaults to base (a no-op
# duplicate) so only services that set it copy/depend on that extras file — editing
# requirements-food.txt then doesn't bust the pip layer of any other service.
ARG EXTRA_REQUIREMENTS_FILE=requirements-base.txt
COPY requirements-base.txt ${EXTRA_REQUIREMENTS_FILE} ./
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_RETRIES=5
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-deps -r requirements-base.txt -r ${EXTRA_REQUIREMENTS_FILE}

# ---- runtime
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv

# Repo-relative dir of the one service this image runs (e.g. services/ev_service,
# or gateway). Only it + shared/ are copied, so a commit to another service leaves
# this image's layers/digest unchanged and compose won't recreate its container.
ARG SERVICE_DIR
COPY shared ./shared
COPY services/__init__.py ./services/__init__.py
COPY ${SERVICE_DIR} ./${SERVICE_DIR}
