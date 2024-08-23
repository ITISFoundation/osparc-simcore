# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.11.9"
FROM --platform=${TARGETPLATFORM} python:${PYTHON_VERSION}-slim-bookworm as base
ARG TARGETPLATFORM
ARG BUILDPLATFORM
RUN echo "I am running on $BUILDPLATFORM, building for $TARGETPLATFORM" > /log
#
#  USAGE:
#     cd sercices/dask-sidecar
#     docker build -f Dockerfile -t dask-sidecar:prod --target production ../../
#     docker run dask-sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN  --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  iputils-ping \
  curl \
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


ENV LANG=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv

ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

# for ARM architecture this helps a lot VS building packages
# NOTE: remove as this might create bad caching behaviour
# ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple


EXPOSE 8080
EXPOSE 8786
EXPOSE 8787

# create dask configuration folder
RUN mkdir --parents /home/scu/.config/dask \
  && chown -R scu:scu /home/scu/.config

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM base as build

ENV SC_BUILD_TARGET=build

RUN  --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential

# NOTE: install https://github.com/astral-sh/uv ultra-fast rust-based pip replacement
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install uv~=0.2

# NOTE: python virtualenv is used here such that installed packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}"

RUN --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install --upgrade  \
  pip~=24.0  \
  wheel \
  setuptools

WORKDIR /build

# install base 3rd party dependencies (NOTE: this speeds up devel mode)
RUN \
  --mount=type=bind,source=services/dask-sidecar/requirements/_base.txt,target=_base.txt \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement _base.txt

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/dask-sidecar [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps

WORKDIR /build/services/dask-sidecar

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/dask-sidecar,target=/build/services/dask-sidecar,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement requirements/prod.txt \
  && uv pip list

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/dask-sidecar [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# ensure home folder is read/writable for user scu
RUN chown -R scu /home/scu
# bring installed package without build tools
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=scu:scu services/dask-sidecar/docker services/dask-sidecar/docker
RUN chmod +x services/dask-sidecar/docker/*.sh


# WARNING: This image is used for dask-scheduler and dask-worker.
# In order to have the same healty entrypoint port
# make sure dask worker is started as ``dask-worker --dashboard-address 8787``.
# Otherwise the worker will take random ports to serve the /health entrypoint.
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=5s \
  --retries=5 \
  CMD ["curl", "-Lf", "http://127.0.0.1:8787/health"]

ENTRYPOINT [ "/bin/sh", "services/dask-sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/dask-sidecar/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET=development

WORKDIR /devel
RUN chown -R scu:scu "${VIRTUAL_ENV}"

# NOTE: devel mode does NOT have HEALTHCHECK

ENTRYPOINT [ "/bin/sh", "services/dask-sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/dask-sidecar/docker/boot.sh"]
