# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.11.9"
FROM python:${PYTHON_VERSION}-slim-bookworm as base

LABEL maintainer=pcrespov

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN  --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  git \
  && apt-get clean -y \
  # verify that the binary works
  && git --version

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

RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux && \
  apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential

# NOTE: install https://github.com/astral-sh/uv ultra-fast rust-based pip replacement
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install uv~=0.2

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}"

RUN --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install --upgrade \
  pip~=24.0  \
  wheel \
  setuptools

WORKDIR /build/packages/service-integration

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=packages/service-integration,target=/build/packages/service-integration,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement requirements/prod.txt \
  && uv pip list


# -------------------------- Build stage -------------------

FROM base as development
# NOTE: this is necessary to allow to build development images but is the same as production here
FROM base as production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu
# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu

USER scu

COPY --from=build --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# NOTE: do not activate ENV PYTHONOPTIMIZE=TRUE since excutable contains pytest code
ENTRYPOINT [ "ooil" ]
