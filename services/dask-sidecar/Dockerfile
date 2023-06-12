# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.10"
FROM itisfoundation/osparc-base-python:${PYTHON_VERSION} as base
#
#  USAGE:
#     cd sercices/dask-sidecar
#     docker build -f Dockerfile -t dask-sidecar:prod --target production ../../
#     docker run dask-sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg
EXPOSE 8080
EXPOSE 8786
EXPOSE 8787

RUN  --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  iputils-ping \
  curl \
  && apt-get clean -y

# for ARM architecture this helps a lot VS building packages
ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple


# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM itisfoundation/osparc-builder-python:${PYTHON_VERSION} as build

# install base 3rd party dependencies (NOTE: this speeds up devel mode)
RUN \
  --mount=type=bind,source=services/dask-sidecar/requirements/_base.txt,target=_base.txt \
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
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
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  --requirement requirements/prod.txt \
  && pip list -v

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
