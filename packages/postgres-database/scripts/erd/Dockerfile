ARG PYTHON_VERSION="3.10.10"
FROM python:${PYTHON_VERSION}-slim-buster as base

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


RUN pip --no-cache-dir install --upgrade \
  pip~=23.0  \
  wheel \
  setuptools


# devenv
RUN pip install --no-cache-dir \
  pyparsing \
  pydot \
  sqlalchemy_schemadisplay
