ARG PYTHON_VERSION="3.8.10"
FROM python:${PYTHON_VERSION}-slim-buster as base
#
#  USAGE:
#     cd sercices/sidecar
#     docker build -f Dockerfile -t sidecar:prod --target production ../../
#     docker run sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=mguidon

RUN set -eux && \
  apt-get update && \
  apt-get install -y gosu && \
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

# environment variables
ENV SWARM_STACK_NAME=""\
  SIDECAR_INPUT_FOLDER=/home/scu/input \
  SIDECAR_OUTPUT_FOLDER=/home/scu/output \
  SIDECAR_LOG_FOLDER=/home/scu/log

EXPOSE 8080

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

# copy sidecar and dependencies
COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/sidecar /build/services/sidecar
COPY --chown=scu:scu services/storage/client-sdk /build/services/storage/client-sdk

# install base 3rd party dependencies (NOTE: this speeds up devel mode)
RUN pip --no-cache-dir install \
  -r /build/services/sidecar/requirements/_base.txt \
  -r /build/services/sidecar/requirements/_packages.txt

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/sidecar [scu:scu] WORKDIR
#
FROM build as prod-only-deps

WORKDIR /build/services/sidecar
ENV SC_BUILD_TARGET=prod-only-deps
RUN pip --no-cache-dir install -r requirements/prod.txt

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/sidecar [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production
ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# bring installed package without build tools
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}
# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/sidecar/docker services/sidecar/docker

# we use the celery API
HEALTHCHECK --interval=60s \
  --timeout=60s \
  --start-period=30s \
  --retries=3 \
  CMD celery inspect ping -b amqp://${RABBIT_USER}:${RABBIT_PASSWORD}@${RABBIT_HOST}:${RABBIT_PORT} -d sidecar."$(cat ${SIDECAR_HOST_HOSTNAME_PATH})"@${HOSTNAME}

ENTRYPOINT [ "/bin/sh", "services/sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/sidecar/docker/boot.sh"]


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

ENTRYPOINT [ "/bin/sh", "services/sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/sidecar/docker/boot.sh"]
