# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG DOCKER_REGISTRY="itisfoundation"
ARG BASE_TAG="latest"

# -------------------------- Base stage -------------------
# Shared minimal runtime (see services/_base_images/Dockerfile) + git
#
FROM ${DOCKER_REGISTRY}/simcore-runtime-base:${BASE_TAG} AS base

LABEL maintainer=pcrespov

RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  git \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  # verify that the binary works
  && git --version


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

WORKDIR /build/packages/service-integration

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=packages/service-integration,target=/build/packages/service-integration,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip install \
  --requirement requirements/prod.txt \
  && uv pip list


# --------------------------Development stage -------------------
# NOTE: this is necessary to allow to build development images but is the same as production here
FROM base AS development


# --------------------------Production stage -------------------
FROM base AS production

WORKDIR /home/scu
# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu

USER scu

COPY --from=build --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# NOTE: do not activate ENV PYTHONOPTIMIZE=TRUE since executable contains pytest code
ENTRYPOINT [ "ooil" ]
