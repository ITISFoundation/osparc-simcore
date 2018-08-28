FROM python:3.6-alpine as base

LABEL maintainer=pcrespov

#  USAGE:
#     docker build -f Dockerfile -t web:ci --target ci ../../
#     docker run web:ci
#
#  REQUIRED: context expected at $(this-file-dir)/../../
#  REQUIRED: client_qx:build image ready

ARG DOCKER_GID_ARG=1001

# create user 'scu' and adds it to host's docker group
RUN adduser -D -u 8004 scu &&\
    addgroup -g $DOCKER_GID_ARG docker &&\
    addgroup scu docker

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
#
# TODO: try installing in .venv in $HOME would allow installing as non-root all 3rd, 2nd
#       and even the application itself
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

# 1. install base 3rd party packages
COPY --chown=scu:scu services/web/server/requirements requirements
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
VOLUME /home/scu/services/web/server/
VOLUME /home/scu/services/webclient/

USER scu
ENV SIMCORE_WEB_CONFIG development
ENV DEBUG 1
WORKDIR /home/scu/services/web/server
CMD ./boot.sh


# --------------------------Production multi-stage -------------------
FROM build as build-production

ENV SIMCORE_WEB_CONFIG production

# 2. 2nd party packages
COPY --chown=scu:scu packages $HOME/packages
# 3. client
COPY --from=services_webclient:build --chown=scu:scu /home/scu/client/build-output $HOME/services/client
# 4. server
COPY --chown=scu:scu services/web/server $HOME/services/web/server

WORKDIR /home/scu/services/web/server
RUN $PIP --no-cache-dir install -r requirements/prod.txt ;\
    $PIP list

#-------------------
FROM base as production

# TODO: PC->MaG some postgresql missing? install non-dev package!?

COPY --from=build-production --chown=scu:scu $HOME/services/web/server/boot.sh $HOME
COPY --from=build-production --chown=scu:scu $HOME/.venv $HOME/.venv

RUN . $HOME/.venv/bin/activate; pip list

WORKDIR /home/scu
USER scu
ENV DEBUG 0
ENTRYPOINT ./boot.sh
