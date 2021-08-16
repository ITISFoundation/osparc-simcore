ARG PYTHON_VERSION="3.8.10"
FROM python:${PYTHON_VERSION}-slim-buster as base
#
#  USAGE:
#     cd sercices/dask-sidecar
#     docker build -f Dockerfile -t dask-sidecar:prod --target production ../../
#     docker run dask-sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=pcrespov

RUN set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  iputils-ping \
  curl \
  gosu \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
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

ENV SWARM_STACK_NAME="" \
  SIDECAR_INPUT_FOLDER=/home/scu/input \
  SIDECAR_OUTPUT_FOLDER=/home/scu/output \
  SIDECAR_LOG_FOLDER=/home/scu/log


EXPOSE 8080
EXPOSE 8786
EXPOSE 8787


# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM base as build

ENV SC_BUILD_TARGET=build

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*


# NOTE: python virtualenv is used here such that installed packages may be moved to production image easily by copying the venv
RUN python -m venv "${VIRTUAL_ENV}"
RUN pip --no-cache-dir install --upgrade \
  pip~=21.2.3  \
  wheel \
  setuptools

# copy dask-sidecar and dependencies
COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/dask-sidecar /build/services/dask-sidecar
COPY --chown=scu:scu services/storage/client-sdk /build/services/storage/client-sdk
COPY --chown=scu:scu services/sidecar /build/services/sidecar

# install base 3rd party dependencies (NOTE: this speeds up devel mode)
RUN pip --no-cache-dir install \
  -r /build/services/dask-sidecar/requirements/_base.txt \
  -r /build/services/dask-sidecar/requirements/_packages.txt

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/dask-sidecar [scu:scu] WORKDIR
#
FROM build as prod-only-deps

WORKDIR /build/services/dask-sidecar
ENV SC_BUILD_TARGET=prod-only-deps
RUN pip --no-cache-dir install -r requirements/prod.txt

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
# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/dask-sidecar/docker services/dask-sidecar/docker


# WARNING: This image is used for dask-scheduler and dask-worker.
# In order to have the same healty entrypoint port
# make sure dask worker is started as ``dask-worker --dashboard-address 8787``.
# Otherwise the worker will take random ports to serve the /health entrypoint.
HEALTHCHECK \
  --interval=60s \
  --timeout=60s \
  --start-period=10s \
  --retries=3 \
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
