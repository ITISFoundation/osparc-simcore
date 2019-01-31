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
# TODO: tmp workaround for https://github.com/pypa/pip/issues/6197
# - Added explicit --cache-dir that is removed at the end of the build
ENV PIP  /home/scu/.venv/bin/pip3 --cache-dir=/tmp/.pipcache
ENV PIP2 $VENV2/bin/pip --cache-dir=/tmp/.pipcache2

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
      python2-dev \
      linux-headers

RUN python3 -m venv $HOME/.venv &&\
    $PIP install --upgrade \
      pip \
      wheel \
      setuptools &&\
    $PIP list

RUN $PIP install virtualenv &&\
    $VENV3/bin/virtualenv --python=python2 $VENV2

WORKDIR /home/scu

# install base 3rd party packages to accelerate runtime installs
COPY --chown=scu:scu services/storage/requirements/py27.txt requirements-py27.txt
COPY --chown=scu:scu services/storage/requirements/base.txt requirements-base.txt
COPY --chown=scu:scu services/storage/docker docker

RUN $PIP install -r requirements-base.txt
RUN $PIP2 install numpy==1.16.0 &&\
    $PIP2 install -r requirements-py27.txt


# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
FROM build as cache

ENV SIMCORE_WEB_CONFIG production

# 2nd party packages
COPY --chown=scu:scu packages $HOME/packages
# server
COPY --chown=scu:scu services/storage $HOME/services/storage

WORKDIR /home/scu/services/storage
RUN $PIP install -r requirements/prod.txt &&\
    $PIP list


WORKDIR /home/scu
ENV DEBUG 0

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
#
FROM cache as production

# remove any unnecessary stuff
RUN . $HOME/.venv/bin/activate; $PIP list &&\
    rm -rf $HOME/packages &&\
    rm -rf $HOME/services/storage &&\
    rm -rf /tmp/.pipcache &&\
    rm -rf /tmp/.pipcache2


ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD ["/bin/sh", "docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
#
FROM build as development

ARG HOST_GID_ARG=1000

# install test 3rd party packages to accelerate runtime installs
COPY --chown=scu:scu services/storage/tests/requirements.txt requirements-tests.txt
RUN $PIP install -r requirements-tests.txt

# in dev mode we give access to `scu` to host's mapped volumes
RUN addgroup -g $HOST_GID_ARG hgrp &&\
    addgroup scu hgrp &&\
    chown -R scu:scu $HOME/.venv

RUN rm -rf /tmp/.pipcache*

VOLUME /home/scu/packages
VOLUME /home/scu/services/storage

ENV DEBUG 1
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD ["/bin/sh", "docker/boot.sh"]
