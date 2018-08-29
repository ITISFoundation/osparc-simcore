FROM python:3.6-alpine as base

LABEL maintainer=mguidon

ARG DOCKER_GID_ARG=1001

RUN apk add --no-cache \
      su-exec

# create user 'scu' and adds it to host's docker group
RUN adduser -D -u 8004 scu &&\
    addgroup -g $DOCKER_GID_ARG docker &&\
    addgroup scu docker

ENV HOME /home/scu
ENV PIP  /home/scu/.venv/bin/pip3

EXPOSE 8000
VOLUME /home/scu/input
VOLUME /home/scu/output
VOLUME /home/scu/log
#VOLUME /var/run/docker.sock DO NOT EXPOSE .. fails!

# -------------------------- Build stage -------------------
# Keeps same folder structure as in repo so we can reuse relative paths
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

WORKDIR /home/scu

# Build context set at repo's root
COPY --chown=scu:scu services/sidecar/requirements $HOME/requirements
COPY services/sidecar/.docker $HOME/.docker

RUN $PIP install --no-cache-dir -r requirements/base.txt &&\
    rm -rf requirements

# --------------------------Development stage -------------------
FROM build as development

ARG HOST_GID_ARG=1000

# in dev-mode we give access to `scu` to host's mapped volumes
RUN addgroup -g $HOST_GID_ARG hgrp &&\
    addgroup scu hgrp && \
    chown -R scu:scu $HOME/.venv

VOLUME /home/scu/packages
VOLUME /home/scu/services/sidecar

ENV DEBUG 1
WORKDIR /home/scu
ENTRYPOINT [ "/bin/sh", ".docker/entrypoint.sh" ]
CMD $HOME/boot.sh


# --------------------------Production multi-stage -------------------
FROM build as build-production

# Buil context set at repo's root
COPY --chown=scu:scu packages $HOME/packages
COPY --chown=scu:scu services/sidecar $HOME/services/sidecar

WORKDIR /home/scu/services/sidecar
RUN $PIP --no-cache-dir install -r requirements/prod.txt ;\
    $PIP list

#-------------------
FROM base as production

# TODO: PC->MaG some postgresql missing? install non-dev package!?

COPY --from=build-production --chown=scu:scu $HOME/services/sidecar/boot.sh $HOME
COPY --from=build-production --chown=scu:scu $HOME/.venv $HOME/.venv
COPY --from=build-production --chown=scu:scu $HOME/.docker $HOME/.docker

RUN . $HOME/.venv/bin/activate; pip list

ENV DEBUG 0
WORKDIR /home/scu
ENTRYPOINT [ "/bin/sh", ".docker/entrypoint.sh" ]
CMD ./boot.sh
