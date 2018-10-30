FROM python:3.6-alpine as base

LABEL maintainer=mguidon

ARG DOCKER_GID_ARG=1001

RUN apk add --no-cache \
      su-exec

# create user `scu` and `docker` group (with same id as in host)
RUN adduser -D -u 8004 scu &&\
    addgroup -g $DOCKER_GID_ARG docker

ENV HOME /home/scu
ENV PIP  /home/scu/.venv/bin/pip3

EXPOSE 8000
VOLUME /home/scu/input
VOLUME /home/scu/output
VOLUME /home/scu/log

WORKDIR /home/scu

# -------------------------- Build stage -------------------
#
# - Preserves relative folder structure
#
# + /home/scu/              $HOME
#    + services/sidecar
#        ...
#    + packages
#        ...
FROM base as build

RUN apk add --no-cache \
      postgresql-dev \
      gcc \
      libc-dev

RUN python3 -m venv $HOME/.venv &&\
    $PIP install --no-cache-dir --upgrade \
      pip \
      wheel \
      setuptools

# TODO: check if scu:scu copy is necessary!?
COPY --chown=scu:scu services/sidecar/requirements/base.txt requirements-base.txt
RUN $PIP install --no-cache-dir -r requirements-base.txt &&\
    rm requirements-base.txt

COPY --chown=scu:scu services/sidecar/docker docker
COPY --chown=scu:scu services/sidecar/boot.sh boot.sh

# --------------------------Development stage -------------------
FROM build as development

ARG HOST_GID_ARG=1000

# in dev-mode we give access to `scu` to host's mapped volumes
# FIXME: files created by scu cannot be deleted by host! we need to do the same group in host?
RUN addgroup -g $HOST_GID_ARG hgrp &&\
    addgroup scu hgrp && \
    chown -R scu:scu $HOME/.venv

VOLUME /home/scu/packages
VOLUME /home/scu/services/sidecar

ENV DEBUG 1
ENV RUN_DOCKER_ENGINE_ROOT=0
USER root
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD ./boot.sh


# --------------------------Production multi-stage -------------------
#FROM build as build-production
FROM build as production

# TODO: check if scu:scu copy is necessary in all cases!? since we are just installing?
COPY --chown=scu:scu packages $HOME/packages
COPY --chown=scu:scu services/sidecar $HOME/services/sidecar

WORKDIR /home/scu/services/sidecar
RUN $PIP --no-cache-dir install -r requirements/prod.txt ;\
    $PIP list

#-------------------
#FROM base as production

# TODO: PC Reduce docker size by installing only non-dev

#COPY --from=build-production --chown=scu:scu $HOME/boot.sh boot.sh
#COPY --from=build-production --chown=scu:scu $HOME/.venv .venv
#COPY --from=build-production --chown=scu:scu $HOME/docker docker

WORKDIR /home/scu/

RUN . $HOME/.venv/bin/activate; pip list &&\
    rm -rf $HOME/services

ENV DEBUG 0
ENV RUN_DOCKER_ENGINE_ROOT=0
USER root
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD ["/bin/sh", "./boot.sh"]
