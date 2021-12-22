ARG PYTHON_VERSION="3.8.10"
FROM python:${PYTHON_VERSION}-slim-buster as base
#
#  USAGE:
#     cd sercices/dynamic-sidecar
#     docker build -f Dockerfile -t dynamic-sidecar:prod --target production ../../
#     docker run dynamic-sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer="Andrei Neagu <neagu@itis.swiss>"

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
# directory where dynamic-sidecar stores creates and shares
# volumes between itself and the spawned containers
ENV DY_VOLUMES="/dy-volumes"


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

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN python -m venv ${VIRTUAL_ENV}
RUN mkdir -p ${DY_VOLUMES}

RUN pip install --upgrade --no-cache-dir \
  pip~=21.3  \
  wheel \
  setuptools

WORKDIR /build

# install base 3rd party dependencies
# NOTE: copies to /build to avoid overwriting later which would invalidate this layer
COPY --chown=scu:scu services/dynamic-sidecar/requirements/_base.txt .
RUN pip --no-cache-dir install -r _base.txt

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/dynamic-sidecar [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET prod-only-deps

COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/dynamic-sidecar /build/services/dynamic-sidecar

WORKDIR /build/services/dynamic-sidecar

RUN pip --no-cache-dir install -r requirements/prod.txt &&\
  pip --no-cache-dir list -v


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/dynamic-sidecar [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --chown=scu:scu --from=prod-only-deps  ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=scu:scu --from=prod-only-deps  ${DY_VOLUMES} ${DY_VOLUMES}

# Copies booting scripts
COPY --chown=scu:scu services/dynamic-sidecar/docker services/dynamic-sidecar/docker
RUN chmod +x services/dynamic-sidecar/docker/*.sh

# improoving boot times by disabling the healtcheck
# in oder to have similar performance a more aggressive healethcek
# would be required.
# since the director-v2 already keeps track of this service
# removing the healthchek is not an issue
HEALTHCHECK NONE

EXPOSE 8000

ENTRYPOINT [ "/bin/sh", "services/dynamic-sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/dynamic-sidecar/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as myu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET=development

WORKDIR /devel

RUN chown -R scu:scu ${VIRTUAL_ENV}
RUN chown -R scu:scu ${DY_VOLUMES}

EXPOSE 8000
EXPOSE 3000

ENTRYPOINT ["/bin/sh", "services/dynamic-sidecar/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/dynamic-sidecar/docker/boot.sh"]
