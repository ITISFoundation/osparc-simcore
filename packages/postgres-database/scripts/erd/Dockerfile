# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG PYTHON_VERSION="3.13.9"
# NOTE: pinned exactly due to https://github.com/astral-sh/uv/issues/21692 (fixed in uv > 0.12.14)
ARG UV_VERSION="0.12.13"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build
# we docker image is built based on debian
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

RUN apt-get update \
  && apt-get -y install --no-install-recommends\
  make \
  libc-dev \
  graphviz-dev \
  git \
  gcc \
  gawk \
  graphviz \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/

# devenv
COPY requirements.txt requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements.txt
