ARG PYTHON_VERSION="3.6.10"
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

RUN apt-get update &&\
  apt-get install -y --no-install-recommends \
  build-essential \
  git

# NOTE: python virtualenv is used here such that installed packages may be moved to production image easily by copying the venv
RUN python -m venv ${VIRTUAL_ENV}

RUN pip --no-cache-dir install --upgrade \
  pip~=20.2.2  \
  wheel \
  setuptools

WORKDIR /build

# install only base 3rd party dependencies
COPY  --chown=scu:scu packages/postgres-database/ .
RUN pip --no-cache-dir --quiet install .[migration]



# --------------------------------------------
FROM base as production

ENV PYTHONOPTIMIZE=TRUE

# testing defaults
ENV POSTGRES_USER=scu \
  POSTGRES_PASSWORD=adminadmin \
  POSTGRES_HOST=postgres \
  POSTGRES_PORT=5432 \
  POSTGRES_DB=simcoredb

WORKDIR /home/scu

USER ${SC_USER_NAME}

# bring installed package without build tools
COPY --from=build ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=scu:scu services/migration/docker services/migration/docker

ENTRYPOINT [ "/bin/sh", "services/migration/docker/entrypoint.sh" ]
