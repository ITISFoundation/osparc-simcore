FROM python:3.6-alpine as base
#
#  USAGE:
#     cd sercices/web
#     docker build -f Dockerfile -t web:prod --target production ../../
#     docker run web:ci
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages
#  REQUIRED: client_qx:build image ready

LABEL maintainer=pcrespov


# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
RUN adduser -D -u 8004 -s /bin/sh -h /home/scu scu

RUN apk add --no-cache \
      su-exec

ENV PATH "/home/scu/.local/bin:$PATH"

ENV SC_PIP  pip --no-cache-dir
# TODO: rename with common prefix!
ENV SIMCORE_WEB_OUTDIR /home/scu/services/web/client
# TODO: eliminate this variable!
ENV IS_CONTAINER_CONTEXT Yes

ENV SC_BUILD_TARGET base
ENV SC_BOOT_MODE default

EXPOSE 8080

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#    + packages
#    + services/web/client         $SIMCORE_WEB_OUTDIR
#       - index.html
#        ...
#    + services/web/server
#       + src
#       + tests

FROM base as build

ENV SC_BUILD_TARGET build

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
      libc-dev \
      libffi-dev

RUN $SC_PIP install --upgrade \
      pip~=20.0.2 \
      wheel \
      setuptools

WORKDIR /build

# install base 3rd party dependencies
COPY  --chown=scu:scu services/web/server/requirements/*.txt \
      tmp/web/server/requirements/

RUN $SC_PIP install \
      -r tmp/web/server/requirements/_base.txt


# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/web/server [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache

# 2nd party packages
COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/web/server /build/services/web/server

WORKDIR /build/services/web/server

RUN $SC_PIP install -r requirements/prod.txt &&\
    $SC_PIP list -v

# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + docker
#
FROM cache as production

ENV SC_BUILD_TARGET production
ENV PYTHONOPTIMIZE=TRUE

# front-end client last (image name is the path to the Dockerfile)
COPY --from=client/tools/qooxdoo-kit/builder:latest --chown=scu:scu \
  /project/build-output \
  /build/services/web/client

WORKDIR /home/scu

RUN mkdir -p services/web/server &&\
    chown scu:scu services/web/server &&\
    mv /build/services/web/server/docker services/web/server/docker &&\
    mv /build/services/web/client ${SIMCORE_WEB_OUTDIR} &&\
    rm -rf /build

RUN apk del --no-cache\
      gcc \
      git

ENV SC_HEALTHCHECK_INTERVAL 30
ENV SC_HEALTHCHECK_RETRY 3

HEALTHCHECK --interval=30s \
            --timeout=120s \
            --start-period=30s \
            --retries=3 \
            CMD ["python3", "/home/scu/services/web/server/docker/healthcheck.py", "http://localhost:8080/v0/"]

ENTRYPOINT [ "/bin/sh", "services/web/server/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/web/server/docker/boot.sh"]



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

ENV SIMCORE_WEB_OUTDIR /devel/services/web/client

WORKDIR /devel
VOLUME  /devel/packages
VOLUME  /devel/services/web/server/
VOLUME  /devel/services/web/client/

ENTRYPOINT [ "/bin/sh", "services/web/server/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/web/server/docker/boot.sh"]
