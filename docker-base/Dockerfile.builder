# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.10"
FROM itisfoundation/osparc-base-python:${PYTHON_VERSION}

ENV SC_BUILD_TARGET build

RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=locked \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  git

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN python -m venv "${VIRTUAL_ENV}"

ARG PIP_VERSION="23.1"
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install --upgrade  \
  pip~=${PIP_VERSION}  \
  wheel \
  setuptools

WORKDIR /build
