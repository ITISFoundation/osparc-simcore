# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.11.9"
FROM python:${PYTHON_VERSION}-slim-bookworm as base
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
  && mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  docker-ce-cli=${DOCKER_APT_VERSION} \
  docker-compose-plugin=${DOCKER_COMPOSE_APT_VERSION} \
  gosu \
  libcap2-bin \
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
RUN \
  --mount=type=bind,source=scripts/install_rclone.bash,target=install_rclone.bash \
  ./install_rclone.bash

RUN AWS_CLI_VERSION="2.11.11" \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWS_CLI_VERSION}.zip" -o "awscliv2.zip" \
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
FROM base as build

ENV SC_BUILD_TARGET=build

RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential

# NOTE: install https://github.com/astral-sh/uv ultra-fast rust-based pip replacement
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install uv~=0.2

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}" \
  && mkdir -p "${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}"

RUN --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install --upgrade  \
  pip~=24.0  \
  wheel \
  setuptools


WORKDIR /build

# install base 3rd party dependencies
# NOTE: copies to /build to avoid overwriting later which would invalidate this layer
RUN \
  --mount=type=bind,source=services/dynamic-sidecar/requirements/_base.txt,target=_base.txt \
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  uv pip install \
  --requirement _base.txt

# copy utility devops scripts
COPY --chown=scu:scu services/dynamic-sidecar/scripts/Makefile /home/scu
COPY --chown=root:root services/dynamic-sidecar/scripts/Makefile /root

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/dynamic-sidecar [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET prod-only-deps

WORKDIR /build/services/dynamic-sidecar

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/dynamic-sidecar,target=/build/services/dynamic-sidecar,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement requirements/prod.txt \
  && uv pip list

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/dynamic-sidecar [scu:scu]
#
FROM base as production

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

HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=30s \
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
FROM build as development

ENV SC_BUILD_TARGET=development \
  SC_BOOT_MODE=development

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}" \
  && chown -R scu:scu "${DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}"

EXPOSE 8000
EXPOSE 3000

ENTRYPOINT ["/bin/sh", "services/dynamic-sidecar/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/dynamic-sidecar/docker/boot.sh"]
