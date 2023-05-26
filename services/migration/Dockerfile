# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.10"
FROM python:${PYTHON_VERSION}-slim-buster as base

LABEL maintainer=sanderegg

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN adduser \
  --uid ${SC_USER_ID} \
  --disabled-password \
  --gecos "" \
  --shell /bin/sh \
  --home /home/${SC_USER_NAME} \
  ${SC_USER_NAME}


# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8
# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv
# Ensures that the python and pip executables used
# in the image will be those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"


# --------------------------------------------
FROM base as build

RUN --mount=type=cache,id=basecache,target=/var/cache/apt,mode=0755,sharing=locked \
  --mount=type=cache,id=baseapt,target=/var/lib/apt,mode=0755,sharing=locked \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  git \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*


# NOTE: python virtualenv is used here such that installed packages may be moved to production image easily by copying the venv
RUN python -m venv "${VIRTUAL_ENV}"

RUN --mount=type=cache,mode=0777,target=/root/.cache/pip \
  pip --no-cache-dir install --upgrade  \
  pip~=23.1  \
  wheel \
  setuptools

WORKDIR /build

# install only base 3rd party dependencies
COPY  --chown=scu:scu packages/postgres-database/ .
RUN pip --no-cache-dir --quiet \
  install \
  -r requirements/prod.txt \
  && pip freeze



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

# bring installed package without build tools
COPY --chown=scu:scu --from=build ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=scu:scu services/migration/docker services/migration/docker
# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu
HEALTHCHECK \
  --interval=5s \
  --timeout=10s \
  --start-period=1ms \
  --retries=10 \
  CMD [ "/bin/sh", "/home/scu/services/migration/docker/healthcheck.sh"]

ENTRYPOINT [ "/bin/sh", "services/migration/docker/entrypoint.sh" ]
