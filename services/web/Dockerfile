FROM python:3.6-alpine as base

LABEL maintainer=pcrespov

#  USAGE:
#     docker build -f Dockerfile -t web:ci --target ci ../../
#     docker run web:ci
#
#  REQUIRED: context expected at $(this-file-dir)/../../
#  REQUIRED: client_qx:build image ready

# create user 'scu'
RUN adduser -D -u 8004 scu

ENV HOME /home/scu
ENV PIP  /home/scu/.venv/bin/pip3
ENV SIMCORE_WEB_OUTDIR $HOME/services/web/client
ENV IS_CONTAINER_CONTEXT Yes

EXPOSE 8080

# -------------------------- Build stage -------------------
#
# + /home/scu/              $HOME
#    + packages
#    + services/web/client         $SIMCORE_WEB_OUTDIR
#       - index.html
#        ...
#    + services/web/server
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
      libc-dev \
      libffi-dev

RUN python3 -m venv $HOME/.venv &&\
    $PIP install --no-cache-dir --upgrade \
      pip \
      wheel \
      setuptools

WORKDIR /home/scu

# install base 3rd party packages to accelerate runtime installs
COPY --chown=scu:scu services/web/server/requirements/base.txt requirements-base.txt
RUN $PIP install --no-cache-dir -r requirements-base.txt

# --------------------------Development stage -------------------
FROM build as development

ARG HOST_GID_ARG=1000

# install test 3rd party packages to accelerate runtime installs
COPY --chown=scu:scu services/web/server/requirements/tests.txt requirements-tests.txt
RUN $PIP install --no-cache-dir -r requirements-tests.txt

# in dev mode we give access to `scu` to host's mapped volumes
RUN addgroup -g $HOST_GID_ARG hgrp &&\
    addgroup scu hgrp && \
    chown -R scu:scu $HOME/.venv

VOLUME /home/scu/packages
VOLUME /home/scu/services/web/server/
VOLUME /home/scu/services/web/client/

USER scu
ENV SIMCORE_WEB_CONFIG development
ENV DEBUG 1
WORKDIR /home/scu/services/web/server
CMD ./boot.sh


# --------------------------Production multi-stage -------------------
FROM build as build-production

ENV SIMCORE_WEB_CONFIG production

# 2nd party packages
COPY --chown=scu:scu packages $HOME/packages
# client
COPY --from=services_webclient:build --chown=scu:scu /home/scu/client/build-output $HOME/services/web/client
# server
COPY --chown=scu:scu services/web/server $HOME/services/web/server

WORKDIR /home/scu/services/web/server
RUN $PIP --no-cache-dir install -r requirements/prod.txt &&\
    $PIP list

#-------------------
#FROM base as production
# TODO: PC some basic package missing

#COPY --from=build-production --chown=scu:scu $HOME/services/web/server/boot.sh $HOME
#COPY --from=build-production --chown=scu:scu $HOME/.venv $HOME/.venv
#RUN . $HOME/.venv/bin/activate; pip list

# FIXME: temporary solution until found missing packages
FROM build-production as production

RUN chown -R scu:scu $HOME/.venv &&\
    cp $HOME/services/web/server/boot.sh $HOME &&\
    rm -rf $HOME/packages &&\
    rm -rf $HOME/services/web/server

WORKDIR /home/scu
USER scu
ENV DEBUG 0
ENTRYPOINT ./boot.sh
