# syntax=docker/dockerfile:1
# NOTE: This is a first step towards a devcontainer
#       to perform operations like pip-compile or auto-formatting
#       that preserves identical environment across developer machines
#
# Python version can be upgraded if:
#   - Has been patched several times (avoid using the very first release for production)
#   - Can be installed with pyenv (SEE pyenv install --list )
#
#
ARG PYTHON_VERSION="3.11.9"
FROM python:${PYTHON_VERSION}-slim-bookworm as base


RUN apt-get update \
  && apt-get -y install --no-install-recommends\
  make \
  git \
  gawk \
  apt-utils \
  strace \
  graphviz \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean

ARG HOME_DIR
RUN mkdir -p ${HOME_DIR}
COPY .pydeps ${HOME_DIR}/.pydeps

RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install --upgrade \
  pip~=24.0  \
  wheel \
  setuptools


# devenv
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  pydeps
