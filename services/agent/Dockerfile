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
#     cd sercices/agent
#     docker build -f Dockerfile -t agent:prod --target production ../../
#     docker run agent:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=GitHK

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  gosu \
  curl \
  && apt-get clean -y \
  # verify that the binary works
  && gosu nobody true

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

# Ensures that the python and pip executables used in the image will be
# those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

# rclone installation
ARG TARGETARCH
ENV TARGETARCH=${TARGETARCH}
RUN \
  --mount=type=bind,source=scripts/install_rclone.bash,target=/tmp/install_rclone.bash \
  ./tmp/install_rclone.bash

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
RUN uv venv "${VIRTUAL_ENV}"





WORKDIR /build

# install base 3rd party dependencies



# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/agent [scu:scu] WORKDIR
#
FROM build AS prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps

WORKDIR /build/services/agent

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/agent,target=/build/services/agent,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/agent [scu:scu]
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

# Copies booting scripts
COPY --chown=scu:scu services/agent/docker services/agent/docker
RUN chmod +x services/agent/docker/*.sh


# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=20s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "services/agent/docker/healthcheck.py", "http://localhost:8000/health"]

EXPOSE 8000

ENTRYPOINT [ "/bin/sh", "services/agent/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/agent/docker/boot.sh"]


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
  SC_DEVEL_MOUNT=/devel/services/agent

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}"

EXPOSE 8000
EXPOSE 3000

ENTRYPOINT ["/bin/sh", "services/agent/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/agent/docker/boot.sh"]
