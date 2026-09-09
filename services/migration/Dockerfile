# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG DOCKER_REGISTRY="itisfoundation"
ARG BASE_TAG="latest"

# -------------------------- Base stage -------------------
# Shared minimal runtime (see services/_base_images/Dockerfile)
#
FROM ${DOCKER_REGISTRY}/simcore-runtime-base:${BASE_TAG} AS base

LABEL maintainer=sanderegg


# -------------------------- Build stage -------------------
# Shared build toolchain + empty virtualenv (see services/_base_images/Dockerfile) + git
#
FROM ${DOCKER_REGISTRY}/simcore-build-base:${BASE_TAG} AS build

RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  git \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/*

# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

WORKDIR /build/packages/postgres-database

# install only base 3rd party dependencies
RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip install \
  --requirement requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
FROM base AS production

ENV PYTHONOPTIMIZE=TRUE

ENV SC_DONE_MARK_FILE=migration.done

WORKDIR /home/scu

USER ${SC_USER_NAME}

# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu
# bring installed package without build tools
COPY --chown=scu:scu --from=build ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=scu:scu services/migration/docker services/migration/docker

# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=60s \
  --start-interval=1s \
  --retries=5 \
  CMD [ "/bin/sh", "/home/scu/services/migration/docker/healthcheck.sh"]

ENTRYPOINT [ "/bin/sh", "services/migration/docker/entrypoint.sh" ]
