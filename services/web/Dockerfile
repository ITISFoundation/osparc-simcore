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
#     cd sercices/web
#     docker build -f Dockerfile -t web:prod --target production ../../
#     docker run web:ci
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages
#  REQUIRED: client_qx:build image ready


LABEL maintainer=pcrespov

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  curl \
  gosu \
  libmagic1 \
  xz-utils \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  # verify that the binary works
  && gosu nobody true

# install 7zip
ARG TARGETARCH
ENV TARGETARCH=${TARGETARCH}
RUN \
  --mount=type=bind,source=scripts/install_7zip.bash,target=install_7zip.bash \
  ./install_7zip.bash


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


# TODO: eliminate this variable!
ENV IS_CONTAINER_CONTEXT Yes


EXPOSE 8080

# -------------------------- Build stage -------------------
# Creates and installs virtual environment
# Contains all build tools
#
# + /build             WORKDIR
#    + packages
#    + services/web/server
#       + src
#       + tests

FROM base AS build

ENV SC_BUILD_TARGET build

RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  libffi-dev

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/


# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}"





WORKDIR /build



# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/web/server [scu:scu] WORKDIR
#
FROM build AS prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps
# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# 2nd party packages
WORKDIR /build/services/web/server

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/web/server,target=/build/services/web/server,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements/prod.txt \
  && uv pip list

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + docker
#
FROM base AS production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu
# bring installed package without build tools
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/web/server/docker services/web/server/docker
RUN chmod +x services/web/server/docker/*.sh


# healthcheck.
# NOTE: do not forget to update variable
ENV SC_HEALTHCHECK_TIMEOUT=120s
# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=20s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "/home/scu/services/web/server/docker/healthcheck.py", "http://localhost:8080/v0/health"]

# no need to rebuild everything if just these changed
ARG BUILD_DATE
ARG VCS_URL
ARG VCS_REF

ENV SC_BUILD_DATE=${BUILD_DATE} \
  SC_VCS_URL=${VCS_URL} \
  SC_VCS_REF=${VCS_REF}



ENTRYPOINT [ "services/web/server/docker/entrypoint.sh" ]
CMD ["services/web/server/docker/boot.sh"]



# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build AS development

ENV SC_BUILD_TARGET development

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}"

ENTRYPOINT [ "/bin/sh", "services/web/server/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/web/server/docker/boot.sh"]
