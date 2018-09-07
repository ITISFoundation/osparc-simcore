FROM python:3.6-alpine as base

LABEL maintainer=sanderegg

ARG DOCKER_GID_ARG=1001

RUN apk add --no-cache \
    su-exec

# create user `scu` and `docker` group (with same id as in host)
RUN adduser -D -u 8004 scu &&\
    addgroup -g $DOCKER_GID_ARG docker

ENV HOME /home/scu
ENV PIP  /home/scu/.venv/bin/pip3

EXPOSE 8001
ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''

WORKDIR /home/scu

# -------------------------- Build stage -------------------
#
# - Preserves relative folder structure
#
# + /home/scu/              $HOME
#    + services/director
#        ...
#    + packages
#        ...
FROM base as build

RUN apk add --no-cache \
    gcc \
    libc-dev \
    git

# create virtual environment
RUN python3 -m venv $HOME/.venv &&\
    $PIP install --no-cache-dir --upgrade \
      pip \
      wheel \
      setuptools

# this is done to accelerate installation of director later on
COPY --chown=scu:scu services/director/requirements/base.txt requirements-base.txt
RUN $PIP install --no-cache-dir -r requirements-base.txt &&\
    rm requirements-base.txt

COPY --chown=scu:scu services/director/.docker .docker

# --------------------------Development stage -------------------
FROM build as development

ARG HOST_GID_ARG=1000

# in dev-mode we give access to `scu` to host's mapped volumes
# FIXME: files created by scu cannot be deleted by host! we need to do the same group in host?
RUN addgroup -g $HOST_GID_ARG hgrp &&\
    addgroup scu hgrp && \
    chown -R scu:scu $HOME/.venv

VOLUME /home/scu/services/director

ENV DEBUG 1
ENV RUN_DOCKER_ENGINE_ROOT=0
ENTRYPOINT [ "/bin/sh", ".docker/entrypoint.sh" ]
CMD ["/bin/sh", ".docker/boot.sh"]

# --------------------------Production stage -------------------
FROM build as production

ENV DEBUG 0
ENV RUN_DOCKER_ENGINE_ROOT=0
COPY --chown=scu:scu services/director $HOME/services/director
WORKDIR $HOME/services/director
RUN $PIP install --no-cache-dir -r requirements/prod.txt \
    && rm -rf $HOME/services/director
WORKDIR $HOME
ENTRYPOINT [ "/bin/sh", ".docker/entrypoint.sh" ]
CMD ["/bin/sh", ".docker/boot.sh"]
