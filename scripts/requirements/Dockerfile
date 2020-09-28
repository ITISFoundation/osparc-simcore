ARG PYTHON_VERSION="3.6.10"
FROM python:${PYTHON_VERSION}-slim-buster as base


RUN pip --no-cache-dir install --upgrade \
  pip~=20.2.2  \
  wheel \
  setuptools


# devenv
COPY requirements.txt .
RUN pip install -r requirements.txt


WORKDIR /work

# .dockerignore to include only target folders
# mount osparc-simcore -> /work
# cd script
# make reqs
