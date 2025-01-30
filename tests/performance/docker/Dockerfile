# syntax=docker/dockerfile:1


FROM cruizba/ubuntu-dind:latest AS base
ARG PYTHON_VERSION
LABEL maintainer=bisgaard-itis

# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8
ENV UV_PYTHON=${PYTHON_VERSION}

# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv

# Ensures that the python and pip executables used in the image will be
# those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

ENV SC_BUILD_TARGET=build

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  curl \
  git \
  jq

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /uvx /bin/

RUN uv venv "${VIRTUAL_ENV}"

WORKDIR /test
