ARG PYTHON_VERSION="3.6.10"
FROM python:${PYTHON_VERSION}-slim as base
#
#  USAGE:
#     cd sercices/sidecar
#     docker build -f Dockerfile -t sidecar:prod --target production ../../
#     docker run sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=mguidon

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
ENV PATH="/${VIRTUAL_ENV}/bin:$PATH"

# environment variables
ENV SWARM_STACK_NAME=""\
    SIDECAR_SERVICES_MAX_NANO_CPUS=4000000000 \
    SIDECAR_SERVICES_MAX_MEMORY_BYTES=2147483648 \
    SIDECAR_SERVICES_TIMEOUT_SECONDS=1200 \
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

RUN apt-get update &&\
    apt-get install -y --no-install-recommends \
    build-essential

# NOTE: python virtualenv is used here such that installed packages may be moved to production image easily by copying the venv
RUN python -m venv ${VIRTUAL_ENV}

RUN pip --no-cache-dir install --upgrade \
    pip~=20.0.2  \
    wheel \
    setuptools

# copy sidecar and dependencies
COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/sidecar /build/services/sidecar
COPY --chown=scu:scu services/storage/client-sdk /build/services/storage/client-sdk

# install base 3rd party dependencies (NOTE: this speeds up devel mode)
RUN pip --no-cache-dir install -r /build/services/sidecar/requirements/_base.txt

# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/sidecar [scu:scu] WORKDIR
#
FROM build as cache

WORKDIR /build/services/sidecar
ENV SC_BUILD_TARGET=cache
RUN pip --no-cache-dir install -r requirements/prod.txt

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/sidecar [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production
ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# bring installed package without build tools
COPY --from=cache --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}
# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/sidecar/docker services/sidecar/docker
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
ENTRYPOINT [ "/bin/sh", "services/sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/sidecar/docker/boot.sh"]
