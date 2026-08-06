# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG DOCKER_REGISTRY="itisfoundation"
ARG BASE_TAG="latest"

# -------------------------- Base stage -------------------
# Shared minimal runtime (see services/_base_images/Dockerfile)
#
FROM ${DOCKER_REGISTRY}/simcore-runtime-base:${BASE_TAG} AS base
#
#  USAGE:
#     cd services/director
#     docker build -f Dockerfile -t director:prod --target production ../../
#     docker run director:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

EXPOSE 8000
EXPOSE 3000


# -------------------------- Build stage -------------------
# Shared build toolchain + empty virtualenv (see services/_base_images/Dockerfile)
#
FROM ${DOCKER_REGISTRY}/simcore-build-base:${BASE_TAG} AS build


# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/director [scu:scu] WORKDIR
#
FROM build AS prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps

# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

WORKDIR /build/services/director

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/director,target=/build/services/director,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/director [scu:scu]
#
FROM base AS production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu
# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu

# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --chown=scu:scu --from=prod-only-deps  ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copies booting scripts
COPY --chown=scu:scu services/director/docker services/director/docker
RUN chmod +x services/director/docker/*.sh

# Copies healthcheck script for fast execution (python3 -S skips site-packages)
COPY --chown=scu:scu \
  scripts/docker/docker_healthcheck.py \
  docker/healthcheck.py

# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=120s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "-S", "docker/healthcheck.py", "http://localhost:8000/v0/"]

ENTRYPOINT [ "/bin/sh", "services/director/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/director/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build AS development

ENV SC_BUILD_TARGET=development \
  SC_DEVEL_MOUNT=/devel/services/director

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}"

ENTRYPOINT [ "/bin/sh", "services/director/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/director/docker/boot.sh"]
