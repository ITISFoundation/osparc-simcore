# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG PYTHON_VERSION="3.11.9"
ARG UV_VERSION="0.7"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build

FROM python:${PYTHON_VERSION}-slim-bookworm AS base-arm64
# These environment variables are necessary because of https://github.com/astral-sh/uv/issues/6105
# and until https://gitlab.com/qemu-project/qemu/-/issues/2846 gets fixed
ENV UV_CONCURRENT_INSTALLS=1

FROM python:${PYTHON_VERSION}-slim-bookworm AS base-amd64

FROM base-${TARGETARCH} AS base
#
#  USAGE:
#     cd sercices/dynamic-sidecar
#     docker build -f Dockerfile -t dynamic-sidecar:prod --target production ../../
#     docker run dynamic-sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer="Andrei Neagu <neagu@itis.swiss>"

# NOTE: to list the latest version run `make` inside `scripts/apt-packages-versions`
ENV DOCKER_APT_VERSION="5:26.1.4-1~debian.12~bookworm"
ENV DOCKER_COMPOSE_APT_VERSION="2.27.1-1~debian.12~bookworm"

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN \
  --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends\
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
  gosu \
  ca-certificates \
  # required by python-magic
  libmagic1 \
  && apt-get remove -y\
  gnupg \
  lsb-release \
  && apt-get clean -y\
  # verify that the binary works
  && gosu nobody true

# install RClone, we do it in a separate layer such that the cache is not locked forever, as this seems to take a long time
ARG TARGETARCH
ENV TARGETARCH=${TARGETARCH}
RUN \
  --mount=type=bind,source=scripts/install_rclone.bash,target=install_rclone.bash \
  ./install_rclone.bash
# install 7zip
ARG TARGETARCH
ENV TARGETARCH=${TARGETARCH}
RUN \
  --mount=type=bind,source=scripts/install_7zip.bash,target=install_7zip.bash \
  ./install_7zip.bash

RUN AWS_CLI_VERSION="2.11.11" \
  && case "${TARGETARCH}" in \
  "amd64") ARCH="x86_64" ;; \
  "arm64") ARCH="aarch64" ;; \
  *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
  esac \
  && curl "https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}-${AWS_CLI_VERSION}.zip" -o "awscliv2.zip" \
  && apt-get update && apt-get install -y unzip \
  && unzip awscliv2.zip \
  && ./aws/install \
  && apt-get remove --purge -y unzip \
  && rm awscliv2.zip \
  && rm -rf awscliv2 \
  && aws --version

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN adduser \
  --uid ${SC_USER_ID} \
  --disabled-password \
  --gecos "" \
  --shell /bin/sh \
  --home /home/${SC_USER_NAME} \
  ${SC_USER_NAME}

# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8
# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv
# Ensures that the python and pip executables used
# in the image will be those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"
# directory where dynamic-sidecar stores creates and shares
# volumes between itself and the spawned containers
ENV DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR="/dy-volumes"

# create direcotry to persist SharedStore data accessiable
# between dynamic-sidecar reboots
ENV DYNAMIC_SIDECAR_SHARED_STORE_DIR="${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}/shared-store"
RUN mkdir -p "${DYNAMIC_SIDECAR_SHARED_STORE_DIR}" && \
  chown -R scu:scu "${DYNAMIC_SIDECAR_SHARED_STORE_DIR}"

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM base AS build

ENV SC_BUILD_TARGET=build

RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}" \
  && mkdir -p "${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}"


RUN --mount=type=cache,target=/root/.cache/uv \
  echo ${UV_CONCURRENT_INSTALLS} && \
  uv pip install --upgrade  \
  wheel \
  setuptools


WORKDIR /build


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
# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

WORKDIR /home/scu

# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu
# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --chown=scu:scu --from=prod-only-deps  ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=scu:scu --from=prod-only-deps  ${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR} ${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}

# Copies booting scripts
COPY --chown=scu:scu services/dynamic-sidecar/docker services/dynamic-sidecar/docker
RUN chmod +x services/dynamic-sidecar/docker/*.sh

# NOTE: the start period of 3 minutes is to allow the dynamic-sidecar
# enough time to connect to the externald dependencies. some times the docker
# networks take time to get created
# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=180s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "services/dynamic-sidecar/docker/healthcheck.py", "http://localhost:8000/health"]

EXPOSE 8000

ENTRYPOINT [ "/bin/sh", "services/dynamic-sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/dynamic-sidecar/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as myu with same gid/uid as host
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
