# TODO: this is still not finished!!
FROM python:3.6-alpine as base

LABEL maintainer=mguidon

#  USAGE:
#     cd sercices/storage
#     docker build -f Dockerfile -t storage:prod --target production ../../
#     docker run storage:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

# non-root user 'scu'
RUN adduser -D -u 8004 scu

RUN apk add --no-cache \
      su-exec

ENV HOME /home/scu
ENV VENV /home/scu/.venv/
ENV VENV3 $VENV
ENV VENV2 /home/scu/.venv27/
ENV PIP  /home/scu/.venv/bin/pip3
ENV PIP2 $VENV2/bin/pip

EXPOSE 8080

# -------------------------- Build stage -------------------
#
# + /home/scu/              $HOME
#    + packages
#        ...
#    + services/storage
#       + src
#       + tests
#
#
# TODO: straight copying python packages bring unnecessary files (e.g. __pycache__) -> dockerignore!
#       could copy and then python setup.py install OR git clone into the container.
#       This applies for both
#
FROM base as build

RUN apk add --no-cache \
      postgresql-dev \
      gcc \
      g++ \
      libc-dev \
      libffi-dev \
      python2 \
      python2-dev

RUN python3 -m venv $HOME/.venv &&\
    $PIP install --no-cache-dir --upgrade \
      pip \
      wheel \
      setuptools

RUN $PIP install virtualenv &&\
    $VENV3/bin/virtualenv --python=python2  $VENV2

WORKDIR /home/scu


# install base 3rd party packages to accelerate runtime installs
COPY --chown=scu:scu services/storage/requirements/py27.txt requirements-py27.txt
COPY --chown=scu:scu services/storage/requirements/base.txt requirements-base.txt
COPY --chown=scu:scu services/storage/docker docker
RUN $PIP install --no-cache-dir -r requirements-base.txt

RUN apk add --no-cache \
  linux-headers
RUN $PIP2 install --no-cache-dir -r requirements-py27.txt
# --------------------------Development stage -------------------
FROM build as development

ARG HOST_GID_ARG=1000

# install test 3rd party packages to accelerate runtime installs
COPY --chown=scu:scu services/storage/tests/requirements.txt requirements-tests.txt
RUN $PIP install --no-cache-dir -r requirements-tests.txt

# in dev mode we give access to `scu` to host's mapped volumes
RUN addgroup -g $HOST_GID_ARG hgrp &&\
    addgroup scu hgrp && \
    chown -R scu:scu $HOME/.venv

VOLUME /home/scu/packages
VOLUME /home/scu/services/storage/

ENV DEBUG 1
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD docker/boot.sh


# --------------------------Production multi-stage -------------------
#FROM build as build-production
FROM build as dependencies

ENV SIMCORE_WEB_CONFIG production

# 2nd party packages
COPY --chown=scu:scu packages $HOME/packages
# server
COPY --chown=scu:scu services/storage $HOME/services/storage

WORKDIR /home/scu/services/storage
RUN $PIP --no-cache-dir install -r requirements/prod.txt &&\
    $PIP list

#-------------------
#FROM base as production
# TODO: PC some basic package missing

#COPY --from=build-production --chown=scu:scu $HOME/services/server/boot.sh $HOME
#COPY --from=build-production --chown=scu:scu $HOME/.venv $HOME/.venv
#RUN . $HOME/.venv/bin/activate; pip list

# FIXME: temporary solution until found missing packages
WORKDIR /home/scu

ENV DEBUG 0
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD docker/boot.sh

FROM dependencies as production
# remove any unnecessary stuff
RUN . $HOME/.venv/bin/activate; pip list &&\
    rm -rf $HOME/packages &&\
    rm -rf $HOME/services/storage