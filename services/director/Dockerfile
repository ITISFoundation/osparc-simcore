ARG PYTHON_VERSION="3.6.10"
FROM python:${PYTHON_VERSION}-slim-buster as base
#
#  USAGE:
#     cd sercices/director
#     docker build -f Dockerfile -t director:prod --target production ../../
#     docker run director:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

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
ENV REGISTRY_AUTH='' \
      REGISTRY_USER='' \
      REGISTRY_PW='' \
      REGISTRY_URL='' \
      REGISTRY_VERSION='v2' \
      PUBLISHED_HOST_NAME='' \
      SIMCORE_SERVICES_NETWORK_NAME='' \
      EXTRA_HOSTS_SUFFIX='undefined'


EXPOSE 8080

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#

FROM base as build

ENV SC_BUILD_TARGET=build

RUN apt-get update \
      &&  apt-get install -y --no-install-recommends \
      build-essential \
      git \
      && apt-get clean \
      && rm -rf /var/lib/apt/lists/*


# NOTE: python virtualenv is used here such that installed packages may be moved to production image easily by copying the venv
RUN python -m venv "${VIRTUAL_ENV}"

RUN pip --no-cache-dir install --upgrade \
      pip~=21.3  \
      wheel \
      setuptools

# copy director and dependencies
COPY  --chown=scu:scu packages /build/packages
COPY  --chown=scu:scu services/director /build/services/director

# install base 3rd party dependencies (NOTE: this speeds up devel mode)
RUN pip --no-cache-dir install -r /build/services/director/requirements/_base.txt

# FIXME:
# necessary to prevent duplicated files.
# Will be removed when director is refactored using cookiecutter as this will not be necessary anymore
COPY --chown=scu:scu api/specs/common/schemas/node-meta-v0.0.1.json \
      /build/services/director/src/simcore_service_director/api/v0/oas-parts/schemas/node-meta-v0.0.1.json

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/director [scu:scu] WORKDIR
#
FROM build as prod-only-deps

WORKDIR /build/services/director
ENV SC_BUILD_TARGET=prod-only-deps
RUN pip --no-cache-dir install -r requirements/prod.txt

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/director [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production \
      SC_BOOT_MODE=production
ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# bring installed package without build tools
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/director/docker services/director/docker
RUN chmod +x services/director/docker/*.sh

HEALTHCHECK --interval=30s \
      --timeout=120s \
      --start-period=30s \
      --retries=3 \
      CMD ["python3", "/home/scu/services/director/docker/healthcheck.py", "http://localhost:8080/v0/"]
ENTRYPOINT [ "services/director/docker/entrypoint.sh" ]
CMD ["services/director/docker/boot.sh"]


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
ENV NODE_SCHEMA_LOCATION=../../../api/specs/common/schemas/node-meta-v0.0.1.json
WORKDIR /devel
RUN chown -R scu:scu "${VIRTUAL_ENV}"
ENTRYPOINT [ "/bin/sh", "services/director/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/director/docker/boot.sh"]
