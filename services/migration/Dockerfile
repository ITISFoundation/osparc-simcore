# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.10"
FROM itisfoundation/osparc-base-python:${PYTHON_VERSION} as base

LABEL maintainer=sanderegg


# --------------------------------------------
FROM itisfoundation/osparc-builder-python:${PYTHON_VERSION} as build


WORKDIR /build/packages/postgres-database

# install only base 3rd party dependencies
RUN \
  --mount=type=bind,source=packages/postgres-database,target=/build/packages/postgres-database,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  --requirement requirements/prod.txt \
  && pip list -v


# --------------------------------------------
FROM base as production

ENV PYTHONOPTIMIZE=TRUE

# testing defaults
ENV POSTGRES_USER=scu \
  POSTGRES_PASSWORD=adminadmin \
  POSTGRES_HOST=postgres \
  POSTGRES_PORT=5432 \
  POSTGRES_DB=simcoredb \
  SC_DONE_MARK_FILE=migration.done


WORKDIR /home/scu

USER ${SC_USER_NAME}

# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu
# bring installed package without build tools
COPY --chown=scu:scu --from=build ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=scu:scu services/migration/docker services/migration/docker

HEALTHCHECK \
  --interval=5s \
  --timeout=10s \
  --start-period=1ms \
  --retries=10 \
  CMD [ "/bin/sh", "/home/scu/services/migration/docker/healthcheck.sh"]

ENTRYPOINT [ "/bin/sh", "services/migration/docker/entrypoint.sh" ]
