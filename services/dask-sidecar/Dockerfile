# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG DOCKER_REGISTRY="itisfoundation"
ARG BASE_TAG="latest"

# -------------------------- Base stage -------------------
# Shared minimal runtime (see services/_base_images/Dockerfile) + iputils-ping + curl
#
FROM ${DOCKER_REGISTRY}/simcore-runtime-base:${BASE_TAG} AS base
#
#  USAGE:
#     cd services/dask-sidecar
#     docker build -f Dockerfile -t dask-sidecar:prod --target production ../../
#     docker run dask-sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  iputils-ping \
  curl \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/*

EXPOSE 8080
EXPOSE 8786
EXPOSE 8787

# create dask configuration folder
RUN mkdir --parents /home/scu/.config/dask \
  && chown -R scu:scu /home/scu/.config


# -------------------------- Build stage -------------------
# Shared build toolchain + empty virtualenv (see services/_base_images/Dockerfile)
#
FROM ${DOCKER_REGISTRY}/simcore-build-base:${BASE_TAG} AS build


# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/dask-sidecar [scu:scu] WORKDIR
#
FROM build AS prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps
# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

WORKDIR /build/services/dask-sidecar

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/dask-sidecar,target=/build/services/dask-sidecar,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/dask-sidecar [scu:scu]
#
FROM base AS production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu
# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu

# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copies booting scripts
COPY --chown=scu:scu services/dask-sidecar/docker services/dask-sidecar/docker
RUN chmod +x services/dask-sidecar/docker/*.sh

# Copies healthcheck script for fast execution (python3 -S skips site-packages)
COPY --chown=scu:scu \
  scripts/docker/docker_healthcheck.py \
  docker/healthcheck.py

# WARNING: This image is used for dask-scheduler and dask-worker.
# In order to have the same healthy entrypoint port
# make sure dask worker is started as ``dask-worker --dashboard-address 8787``.
# Otherwise the worker will take random ports to serve the /health entrypoint.
# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=120s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "-S", "docker/healthcheck.py", "http://127.0.0.1:8787/health"]

ENTRYPOINT [ "/bin/sh", "services/dask-sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/dask-sidecar/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build AS development

ENV SC_BUILD_TARGET=development

WORKDIR /devel
RUN chown -R scu:scu "${VIRTUAL_ENV}"

# NOTE: devel mode does NOT have HEALTHCHECK

ENTRYPOINT [ "/bin/sh", "services/dask-sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/dask-sidecar/docker/boot.sh"]
