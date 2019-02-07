FROM python:3.6-alpine as base

LABEL maintainer=sanderegg

ARG DOCKER_GID_ARG=1001

RUN apk add --no-cache \
    su-exec

# create user `scu` and `docker` group (with same id as in host)
RUN adduser -D -u 8004 scu &&\
    addgroup -g $DOCKER_GID_ARG docker

ENV HOME /home/scu
# TODO: tmp workaround for https://github.com/pypa/pip/issues/6197
# - Added explicit --cache-dir that is removed at the end of the build
ENV PIP  /home/scu/.venv/bin/pip3 --cache-dir=/tmp/.pipcache
# -----

EXPOSE 8001
ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''
ENV PUBLISHED_HOST_NAME=''
ENV EXTRA_HOSTS_SUFFIX = 'undefined'

# ----------------------------------------------------------------
COPY --chown=scu:scu scripts/docker/healthcheck_curl_host.py /healthcheck/healthcheck_curl_host.py
# will start to run after interval every interval. fails after timeout. fail do not count if during start-period. will do # retries
HEALTHCHECK --interval=10s --timeout=30s --start-period=20s --retries=3 CMD [ "python3", "/healthcheck/healthcheck_curl_host.py", "http://localhost:8001/v0/" ]

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
    $PIP install --upgrade \
      pip \
      wheel \
      setuptools

# this is done to accelerate installation of director later on
COPY --chown=scu:scu services/director/requirements/base.txt requirements-base.txt
RUN $PIP install -r requirements-base.txt &&\
    rm requirements-base.txt

COPY --chown=scu:scu services/director/docker docker

# --------------------------Development stage -------------------
FROM build as development

ARG HOST_GID_ARG=1000

# in dev-mode we give access to `scu` to host's mapped volumes
# FIXME: files created by scu cannot be deleted by host! we need to do the same group in host?
RUN addgroup -g $HOST_GID_ARG hgrp &&\
    addgroup scu hgrp && \
    chown -R scu:scu $HOME/.venv &&\
    rm -rf /tmp/.pipcache

VOLUME /home/scu/services/director
VOLUME /home/scu/packages/service-library

ENV DEBUG 1
ENV RUN_DOCKER_ENGINE_ROOT=0
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD ["/bin/sh", "docker/boot.sh"]

# --------------------------Cache stage -------------------
FROM build as cache
COPY --chown=scu:scu services/director $HOME/services/director
COPY --chown=scu:scu packages/service-library $HOME/packages/service-library
WORKDIR $HOME/services/director
RUN $PIP install -r requirements/prod.txt
WORKDIR $HOME/packages/service-library
# FIXME: is this really requirements/dev or rather requirements/prod.txt?
RUN $PIP install -r requirements/dev.txt


# --------------------------Production stage -------------------
FROM cache as production
WORKDIR $HOME
ENV DEBUG 0
ENV RUN_DOCKER_ENGINE_ROOT=0
RUN rm -rf $HOME/services &&\
    rm -rf $HOME/packages &&\
    rm -rf /tmp/.pipcache

ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD ["/bin/sh", "docker/boot.sh"]
