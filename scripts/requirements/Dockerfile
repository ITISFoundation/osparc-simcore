# NOTE: This is a first step towards a devcontainer
#       to perform operations like pip-compile or auto-formatting
#       that preserves identical environment across developer machines
#
ARG PYTHON_VERSION="3.6.10"
FROM python:${PYTHON_VERSION}-slim-buster as base


RUN apt-get update \
  && apt-get -y install --no-install-recommends\
  make \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean


RUN pip --no-cache-dir install --upgrade \
  pip~=20.2.2  \
  wheel \
  setuptools


# devenv
RUN pip install \
  black \
  isort \
  pip-tools \
  bump2version \
  rope
