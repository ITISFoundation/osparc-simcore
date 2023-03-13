ARG PYTHON_VERSION="3.9.12"
FROM python:${PYTHON_VERSION}-slim-buster as base
#
#  USAGE:
#     cd sercices/web
#     docker build -f Dockerfile -t web:prod --target production ../../
#     docker run web:ci
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages
#  REQUIRED: client_qx:build image ready


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


# TODO: eliminate this variable!
ENV IS_CONTAINER_CONTEXT Yes


EXPOSE 8080

# -------------------------- Build stage -------------------
# Creates and installs virtual environment
# Contains all build tools
#
# + /build             WORKDIR
#    + packages
#    + services/web/server
#       + src
#       + tests

FROM base as build

ENV SC_BUILD_TARGET build

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  libmagic1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*


# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN python -m venv "${VIRTUAL_ENV}"

RUN pip --no-cache-dir install --upgrade \
  pip~=23.0  \
  wheel \
  setuptools

WORKDIR /build

# install only base 3rd party dependencies
COPY  --chown=scu:scu services/web/server/requirements/_base.txt requirements_base.txt
RUN pip --no-cache-dir --quiet install -r requirements_base.txt

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/web/server [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET prod-only-deps

# 2nd party packages
COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/web/server /build/services/web/server

WORKDIR /build/services/web/server

RUN pip --no-cache-dir --quiet install -r requirements/prod.txt

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + docker
#
FROM base as production

ARG BUILD_DATE
ARG VCS_URL
ARG VCS_REF

WORKDIR /home/scu

# bring installed package without build tools
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# libmagic is requried by the exporter
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  libmagic1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/web/server/docker services/web/server/docker
RUN chmod +x services/web/server/docker/*.sh


# healthcheck.
# NOTE: do not forget to update variable
ENV SC_HEALTHCHECK_TIMEOUT=120s
HEALTHCHECK --interval=30s \
  --timeout=120s \
  --start-period=30s \
  --retries=3 \
  CMD ["python3", "/home/scu/services/web/server/docker/healthcheck.py", "http://localhost:8080/v0/health"]


ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production \
  SC_BUILD_DATE=${BUILD_DATE} \
  SC_VCS_URL=${VCS_URL} \
  SC_VCS_REF=${VCS_REF}

ENV PYTHONOPTIMIZE=TRUE

ENTRYPOINT [ "services/web/server/docker/entrypoint.sh" ]
CMD ["services/web/server/docker/boot.sh"]



# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET development

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}"

ENTRYPOINT [ "/bin/sh", "services/web/server/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/web/server/docker/boot.sh"]
