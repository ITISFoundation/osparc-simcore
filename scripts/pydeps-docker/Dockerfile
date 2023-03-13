# NOTE: This is a first step towards a devcontainer
#       to perform operations like pip-compile or auto-formatting
#       that preserves identical environment across developer machines
#
# Python version can be upgraded if:
#   - Has been patched several times (avoid using the very first release for production)
#   - Can be installed with pyenv (SEE pyenv install --list )
#
#
ARG PYTHON_VERSION="3.9.12"
FROM python:${PYTHON_VERSION}-slim-buster as base


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

RUN pip --no-cache-dir install --upgrade \
  pip~=23.0  \
  wheel \
  setuptools


# devenv
RUN pip install \
  pydeps
