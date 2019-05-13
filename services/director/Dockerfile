FROM python:3.6-alpine as base
#
#  USAGE:
#     cd sercices/director
#     docker build -f Dockerfile -t director:prod --target production ../../
#     docker run director:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
RUN adduser -D -u 8004 -s /bin/sh -h /home/scu scu

RUN apk add --no-cache \
      su-exec

ENV PATH "/home/scu/.local/bin:$PATH"

# All SC_ variables are customized
ENV SC_PIP pip3 --no-cache-dir
ENV SC_BUILD_TARGET base

# TODO: update environs
ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''
ENV PUBLISHED_HOST_NAME=''
ENV EXTRA_HOSTS_SUFFIX = 'undefined'


EXPOSE 8080

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#

FROM base as build

ENV SC_BUILD_TARGET build

# Installing client libraries and any other package you need
#
# - client library for PostgreSQL https://www.postgresql.org/docs/9.5/libpq.html
#
RUN apk update && \
    apk add --no-cache \
      libpq

# Installing build dependencies (will be deleted in production)
RUN apk add --virtual .build-deps \
      git \
      gcc \
      libc-dev \
      python-dev \
      musl-dev \
      libffi-dev \
      postgresql-dev


RUN $SC_PIP install --upgrade \
      pip~=19.1.1  \
      wheel \
      setuptools

WORKDIR /build

# install base 3rd party dependencies
COPY  --chown=scu:scu services/director/requirements/*.txt \
      tmp/director/requirements/

RUN $SC_PIP install \
      -r tmp/director/requirements/_base.txt

#--------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/director [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache


COPY --chown=scu:scu packages/service-library /build/packages/service-library
COPY --chown=scu:scu services/director /build/services/director

# FIXME:
# necessary to prevent duplicated files.
# Will be removed when director is refactored using cookiecutter as this will not be necessary anymore
COPY --chown=scu:scu api/specs/shared/schemas/node-meta-v0.0.1.json /build/services/director/src/simcore_service_director/oas3/v0/schemas/node-meta-v0.0.1.json

WORKDIR /build/services/director


RUN $SC_PIP install -r requirements/prod.txt &&\
    $SC_PIP list -v


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/director [scu:scu]
#
FROM cache as production


ENV SC_BUILD_TARGET production
ENV SC_BOOT_MODE production

WORKDIR /home/scu

RUN mkdir -p services/director &&\
    chown scu:scu services/director &&\
    mv /build/services/director/docker services/director/docker &&\
    rm -rf /build

RUN apk del --no-cache .build-deps

HEALTHCHECK --interval=30s \
            --timeout=120s \
            --start-period=30s \
            --retries=3 \
            CMD ["python3", "/home/scu/services/director/docker/healthcheck.py", "http://localhost:8080/v0/"]

ENTRYPOINT [ "/bin/sh", "services/director/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/director/docker/boot.sh"]


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
ENV SC_BOOT_MODE development


# WORKDIR /build
# NOTE: can copy from /build if necessary

WORKDIR /devel
VOLUME  /devel/packages
VOLUME  /devel/services/director/
VOLUME /devel/services/api
ENV NODE_SCHEMA_LOCATION ../../../api/specs/shared/schemas/node-meta-v0.0.1.json

ENTRYPOINT [ "/bin/sh", "services/director/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/director/docker/boot.sh"]
