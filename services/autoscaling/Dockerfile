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
#     cd services/autoscaling
#     docker build -f Dockerfile -t autoscaling:prod --target production ../../
#     docker run autoscaling:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

# NOTE: to list the latest version run `make` inside `scripts/apt-packages-versions`
ENV DOCKER_APT_VERSION="5:26.1.4-1~debian.12~bookworm"

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
  fd-find \
  gosu \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  && mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  # only the cli is needed and we remove the unnecessary stuff again
  docker-ce-cli=${DOCKER_APT_VERSION} \
  && apt-get remove -y\
  gnupg \
  curl \
  lsb-release \
  && apt-get clean -y\
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

EXPOSE 8000
EXPOSE 3000

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

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/autoscaling [scu:scu] WORKDIR
#
FROM build AS prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps
# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

WORKDIR /build/services/autoscaling

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/autoscaling,target=/build/services/autoscaling,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/autoscaling [scu:scu]
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
COPY --chown=scu:scu services/autoscaling/docker services/autoscaling/docker
RUN chmod +x services/autoscaling/docker/*.sh


# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=20s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "services/autoscaling/docker/healthcheck.py", "http://localhost:8000/"]

ENTRYPOINT [ "/bin/sh", "services/autoscaling/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/autoscaling/docker/boot.sh"]


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
  SC_DEVEL_MOUNT=/devel/services/autoscaling

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}"

ENTRYPOINT ["/bin/sh", "services/autoscaling/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/autoscaling/docker/boot.sh"]
