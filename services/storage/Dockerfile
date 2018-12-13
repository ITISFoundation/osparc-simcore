# --------------------------Development stage -------------------
FROM itisfoundation/storage-build:latest as development

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
FROM itisfoundation/storage-build:latest as production

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

RUN . $HOME/.venv/bin/activate; pip list &&\
    rm -rf $HOME/packages &&\
    rm -rf $HOME/services/storage

ENV DEBUG 0
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh" ]
CMD docker/boot.sh
