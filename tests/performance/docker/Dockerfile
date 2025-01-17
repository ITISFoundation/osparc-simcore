# syntax=docker/dockerfile:1

ARG PYTHON_VERSION="3.11.9"
ARG UV_VERSION="0.4"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

LABEL maintainer=bisgaard-itis

# NOTE: to list the latest version run `make` inside `scripts/apt-packages-versions`
ENV DOCKER_APT_VERSION="5:26.1.4-1~debian.12~bookworm"

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
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

# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8

# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv

# Ensures that the python and pip executables used in the image will be
# those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"


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
  build-essential \
  curl \
  git \
  jq

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/

RUN uv venv "${VIRTUAL_ENV}"

RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install --upgrade  \
  wheel \
  setuptools

WORKDIR /test
