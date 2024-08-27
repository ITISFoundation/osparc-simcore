# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.11.9"
FROM python:${PYTHON_VERSION}-slim-bookworm as base
#
#  USAGE:
#     cd sercices/storage
#     docker build -f Dockerfile -t storage:prod --target production ../../
#     docker run storage:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=mguidon

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  gosu \
  && apt-get clean -y \
  # verify that the binary works
  && gosu nobody true


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


ENV SC_BUILD_TARGET base
ENV SC_BOOT_MODE default

EXPOSE 8080
# -------------------------- -------------------------------



# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#

FROM base as build

ENV SC_BUILD_TARGET build

RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  git

# NOTE: install https://github.com/astral-sh/uv ultra-fast rust-based pip replacement
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install uv~=0.2

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}"

RUN --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install --upgrade  \
  pip~=24.0  \
  wheel \
  setuptools

WORKDIR /build

# install only base 3rd party dependencies
RUN \
  --mount=type=bind,source=services/storage/requirements/_base.txt,target=_base.txt \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement _base.txt

# -------------------------- -------------------------------




# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/storage [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET prod-only-deps

# 2nd party packages
WORKDIR /build/services/storage

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/storage,target=/build/services/storage,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement requirements/prod.txt \
  && uv pip list
# -------------------------- -------------------------------



# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production \
  SC_HEALTHCHECK_INTERVAL=30 \
  SC_HEALTHCHECK_RETRY=3

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu
# bring installed package without build tools
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/storage/docker services/storage/docker
RUN chmod +x services/storage/docker/*.sh

HEALTHCHECK --interval=10s \
  --timeout=15s \
  --start-period=5s \
  --retries=5 \
  CMD ["python3", "/home/scu/services/storage/docker/healthcheck.py", "http://localhost:8080/v0/"]


ENTRYPOINT [ "/bin/sh", "services/storage/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/storage/docker/boot.sh"]
# -------------------------- -------------------------------




# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
#
#  + /devel         WORKDIR
#    + packages  (mounted volume)
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET=development \
  SC_DEVEL_MOUNT=/devel/services/storage/

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}"

ENTRYPOINT [ "/bin/sh", "services/storage/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/storage/docker/boot.sh"]
# -------------------------- -------------------------------
