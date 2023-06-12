# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.10"
FROM itisfoundation/osparc-base-python:${PYTHON_VERSION} as base
#
#  USAGE:
#     cd sercices/web
#     docker build -f Dockerfile -t web:prod --target production ../../
#     docker run web:ci
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages
#  REQUIRED: client_qx:build image ready


LABEL maintainer=pcrespov

# install libmagic1 TODO: GitHK is this still needed?
RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  libmagic1 \
  && apt-get clean -y

# TODO: eliminate this variable! pcrespov what is this?
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

FROM itisfoundation/osparc-builder-python:${PYTHON_VERSION} as build

# install only base 3rd party dependencies
RUN \
  --mount=type=bind,source=services/web/server/requirements/_base.txt,target=_base.txt \
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  --requirement _base.txt

# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/web/server [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET prod-only-deps

# 2nd party packages
WORKDIR /build/services/web/server

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/web/server,target=/build/services/web/server,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  --requirement requirements/prod.txt \
  && pip list -v

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + docker
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# bring installed package without build tools
COPY --from=prod-only-deps --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/web/server/docker services/web/server/docker
RUN chmod +x services/web/server/docker/*.sh


# healthcheck.
# NOTE: do not forget to update variable
ENV SC_HEALTHCHECK_TIMEOUT=120s
HEALTHCHECK --interval=10s \
  --timeout=5s \
  --start-period=10s \
  --retries=5 \
  CMD ["python3", "/home/scu/services/web/server/docker/healthcheck.py", "http://localhost:8080/v0/health"]

# no need to rebuild everything if just these changed
ARG BUILD_DATE
ARG VCS_URL
ARG VCS_REF

ENV SC_BUILD_DATE=${BUILD_DATE} \
  SC_VCS_URL=${VCS_URL} \
  SC_VCS_REF=${VCS_REF}



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
