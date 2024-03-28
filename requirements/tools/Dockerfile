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
ARG PYTHON_VERSION="3.10.10"
FROM python:${PYTHON_VERSION}-slim-buster as base


RUN apt-get update \
  && apt-get -y install --no-install-recommends\
  make \
  git \
  gawk \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean


# SEE bug with pip==22.1 https://github.com/jazzband/pip-tools/issues/1617
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install --upgrade \
  pip~=24.0  \
  wheel \
  setuptools \
  uv


# devenv
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  pip-tools \
  pipreqs \
  pipdeptree && \
  pip list -vv
