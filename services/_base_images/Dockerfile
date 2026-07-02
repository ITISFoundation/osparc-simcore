# syntax=docker/dockerfile:1

#
# Shared base images for all python-based simcore services.
#
#  Produces two images, tagged with a content-hash (see ci/helpers/compute_base_image_tag.bash):
#
#   - ${DOCKER_REGISTRY}/simcore-runtime-base:${BASE_TAG}
#       minimal runtime: python + common apt deps + non-root `scu` user + venv env.
#       Used as parent of every service `production` stage (small final image).
#
#   - ${DOCKER_REGISTRY}/simcore-build-base:${BASE_TAG}
#       runtime-base + build toolchain (build-essential, uv) + empty virtualenv.
#       Used as parent of every service dependency-install / development stage.
#
#  USAGE:
#     docker buildx build -f services/_base_images/Dockerfile --target runtime-base -t simcore-runtime-base .
#     docker buildx build -f services/_base_images/Dockerfile --target build-base   -t simcore-build-base .
#
#  This image needs NO repository files in the build context (only apt + uv).
#

# Define arguments in the global scope
ARG PYTHON_VERSION="3.13.9"
ARG UV_VERSION="0.9"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build


# -------------------------- runtime-base -------------------
# Minimal runtime shared by every service production stage
#
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime-base

LABEL maintainer="osparc-simcore"

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  fd-find \
  gosu \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
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


# -------------------------- build-base -------------------
# runtime-base + build toolchain shared by every service dependency-install stage
#
FROM runtime-base AS build-base

ENV SC_BUILD_TARGET=build

RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/*

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}"

WORKDIR /build
