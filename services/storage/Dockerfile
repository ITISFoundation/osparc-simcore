#FROM python:3.6-alpine as base
FROM itisfoundation/python-with-pandas:3.6-alpine as base
#
#  USAGE:
#     cd sercices/storage
#     docker build -f Dockerfile -t storage:prod --target production ../../
#     docker run storage:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages


LABEL maintainer=mguidon

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
RUN adduser -D -u 8004 -s /bin/sh -h /home/scu scu

RUN apk add --no-cache \
      su-exec


ENV PATH "/home/scu/.local/bin:$PATH"
ENV HOME /home/scu

# All SC_ variables are customized
ENV SC_PIP pip3 --no-cache-dir
ENV SC_PIP2 pip2 --no-cache-dir
ENV SC_BUILD_TARGET base
ENV SC_BOOT_MODE default

EXPOSE 8080

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#

FROM base as build

# Installing client libraries and any other package you need
#
#  libpq: client library for PostgreSQL https://www.postgresql.org/docs/9.5/libpq.html
#  libstdc++: needed in ujson https://github.com/kohlschutter/junixsocket/issues/33
#
RUN apk update && \
    apk add --no-cache \
      libpq \
      libstdc++

RUN apk add --no-cache \
      postgresql-dev \
      gcc \
      g++ \
      libc-dev \
      libffi-dev \
      linux-headers

RUN $SC_PIP install --upgrade \
      pip~=20.0.2  \
      wheel \
      setuptools

WORKDIR /build

# install base 3rd party dependencies
COPY  --chown=scu:scu services/storage/requirements/*.txt \
      tmp/storage/requirements/

RUN $SC_PIP install \
      -r tmp/storage/requirements/_base.txt

# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
#
#  + /devel         WORKDIR
#    + packages  (mounted volume)
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET development
ENV SC_BOOT_MODE debug-ptvsd

WORKDIR /devel
VOLUME  /devel/packages
VOLUME  /devel/services/storage/

ENTRYPOINT [ "/bin/sh", "services/storage/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/storage/docker/boot.sh"]


# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/storage [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache

COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/storage /build/services/storage

WORKDIR /build/services/storage

RUN $SC_PIP install -r requirements/prod.txt &&\
    $SC_PIP list -v

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
#
FROM cache as production

ENV SC_BUILD_TARGET production
ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

RUN mkdir -p services/storage && chown scu:scu services/storage && \
    mv /build/services/storage/docker services/storage/docker && \
    rm -rf /build

RUN apk del --no-cache\
      gcc

HEALTHCHECK --interval=30s \
            --timeout=120s \
            --start-period=30s \
            --retries=3 \
            CMD ["python3", "/home/scu/services/storage/docker/healthcheck.py", "http://localhost:8080/v0/"]

ENTRYPOINT [ "/bin/sh", "services/storage/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/storage/docker/boot.sh"]
