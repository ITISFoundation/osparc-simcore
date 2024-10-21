# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG PYTHON_VERSION="3.11.9"
ARG UV_VERSION="0.4"
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


RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install --upgrade \
  pip~=24.0  \
  wheel \
  setuptools


# devenv
COPY requirements.txt requirements.txt
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  -r requirements.txt
