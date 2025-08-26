# syntax=docker/dockerfile:1
#
# ERD: Entity Relationship Diagrams
#
# SEE:
#
# - https://erdantic.drivendata.org/stable/
#

ARG PYTHON_VERSION="3.11.9"
ARG UV_VERSION="0.7"
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


COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install -r requirements.txt
