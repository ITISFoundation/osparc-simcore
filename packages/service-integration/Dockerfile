ARG PYTHON_VERSION="3.9.12"
FROM python:${PYTHON_VERSION}-slim-buster as base

LABEL maintainer=pcrespov

RUN set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  gosu && \
  rm -rf /var/lib/apt/lists/* && \
  # verify that the binary works
  gosu nobody true


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



# -------------------------- Build stage -------------------

FROM base as build

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*


# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN python -m venv "${VIRTUAL_ENV}"

RUN pip install --no-cache-dir --upgrade \
  pip~=22.0  \
  wheel \
  setuptools

WORKDIR /build

COPY --chown=scu:scu packages/models-library packages/models-library
COPY --chown=scu:scu packages/service-integration packages/service-integration

# create a venv and install there
RUN make install-prod

# -------------------------- Build stage -------------------

FROM base as production
# New image, copy venv here and add entrypoint and cmd
# COPY

COPY --from=build --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

ENV PYTHONOPTIMIZE=TRUE
ENTRYPOINT [ "ooil" ]
