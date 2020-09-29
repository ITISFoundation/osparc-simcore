ARG PYTHON_VERSION="3.6.10"
FROM python:${PYTHON_VERSION}-slim-buster as base


RUN apt-get update && apt-get install \
  make


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
