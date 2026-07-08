# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG DOCKER_REGISTRY="itisfoundation"
ARG BASE_TAG="latest"

# -------------------------- Base stage -------------------
# Shared minimal runtime (see services/_base_images/Dockerfile)
#   + docker-cli + docker-compose-plugin + libmagic1 + xz-utils + rclone + 7zip
#
FROM ${DOCKER_REGISTRY}/simcore-runtime-base:${BASE_TAG} AS base
#
#  USAGE:
#     cd services/dynamic-sidecar
#     docker build -f Dockerfile -t dynamic-sidecar:prod --target production ../../
#     docker run dynamic-sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=GitHK

# NOTE: to list the latest version run `make` inside `scripts/apt-packages-versions`
ENV DOCKER_APT_VERSION="5:26.1.4-1~debian.12~bookworm"
ENV DOCKER_COMPOSE_APT_VERSION="2.27.1-1~debian.12~bookworm"

RUN \
  --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  xz-utils \
  && mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  docker-ce-cli=${DOCKER_APT_VERSION} \
  docker-compose-plugin=${DOCKER_COMPOSE_APT_VERSION} \
  # required by python-magic
  libmagic1 \
  && apt-get remove -y \
  gnupg \
  lsb-release \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  # verify that the binary works
  && gosu nobody true

# install RClone, we do it in a separate layer such that the cache is not locked forever, as this seems to take a long time
ARG TARGETARCH
ENV TARGETARCH=${TARGETARCH}
RUN \
  --mount=type=bind,source=scripts/install_rclone.bash,target=install_rclone.bash \
  ./install_rclone.bash
# install 7zip
RUN \
  --mount=type=bind,source=scripts/install_7zip.bash,target=install_7zip.bash \
  ./install_7zip.bash

# directory where dynamic-sidecar stores creates and shares
# volumes between itself and the spawned containers
ENV DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR="/dy-volumes"

# create directory to persist SharedStore data accessible
# between dynamic-sidecar reboots
ENV DYNAMIC_SIDECAR_SHARED_STORE_DIR="${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}/shared-store"
RUN mkdir -p "${DYNAMIC_SIDECAR_SHARED_STORE_DIR}" && \
  chown -R scu:scu "${DYNAMIC_SIDECAR_SHARED_STORE_DIR}"

EXPOSE 8000


# -------------------------- Build stage -------------------
# Shared build toolchain + empty virtualenv (see services/_base_images/Dockerfile)
#
FROM ${DOCKER_REGISTRY}/simcore-build-base:${BASE_TAG} AS build

ENV DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR="/dy-volumes"
RUN mkdir -p "${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}"

# copy utility devops scripts
COPY --chown=scu:scu services/dynamic-sidecar/scripts/Makefile /home/scu
COPY --chown=root:root services/dynamic-sidecar/scripts/Makefile /root


# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/dynamic-sidecar [scu:scu] WORKDIR
#
FROM build AS prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps
# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

WORKDIR /build/services/dynamic-sidecar

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/dynamic-sidecar,target=/build/services/dynamic-sidecar,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/dynamic-sidecar [scu:scu]
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
COPY --chown=scu:scu --from=prod-only-deps  ${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR} ${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}

# Copies booting scripts
COPY --chown=scu:scu services/dynamic-sidecar/docker services/dynamic-sidecar/docker
RUN chmod +x services/dynamic-sidecar/docker/*.sh

# Copies healthcheck script for fast execution (python3 -S skips site-packages)
COPY --chown=scu:scu \
  scripts/docker/docker_healthcheck.py \
  docker/healthcheck.py

# NOTE: sometimes docker network may take some time to resolve DNS, thus the longer start-period
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=64s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "-S", "docker/healthcheck.py", "http://localhost:8000/health"]

ENTRYPOINT [ "/bin/sh", "services/dynamic-sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/dynamic-sidecar/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as "scu" with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build AS development

ENV SC_BUILD_TARGET=development \
  SC_BOOT_MODE=development

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}" \
  && chown -R scu:scu "${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}"

EXPOSE 8000
EXPOSE 3000

ENTRYPOINT ["/bin/sh", "services/dynamic-sidecar/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/dynamic-sidecar/docker/boot.sh"]
