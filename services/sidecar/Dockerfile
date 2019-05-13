FROM python:3.6-alpine as base
#
#  USAGE:
#     cd sercices/sidecar
#     docker build -f Dockerfile -t sidecar:prod --target production ../../
#     docker run sidecar:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=mguidon

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
RUN adduser -D -u 8004 -s /bin/sh -h /home/scu scu

RUN apk add --no-cache \
      su-exec

ENV PATH "/home/scu/.local/bin:$PATH"

# All SC_ variables are customized
ENV SC_PIP pip3 --no-cache-dir
ENV SC_BUILD_TARGET base

EXPOSE 8080

VOLUME /home/scu/input
VOLUME /home/scu/output
VOLUME /home/scu/log

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#

FROM base as build

ENV SC_BUILD_TARGET build


RUN apk add --no-cache \
      postgresql-dev \
      gcc \
      libc-dev

RUN $SC_PIP install --upgrade \
      pip~=19.1.1  \
      wheel \
      setuptools

WORKDIR /build

# install base 3rd party dependencies
COPY  --chown=scu:scu services/sidecar/requirements/*.txt \
      tmp/sidecar/requirements/

RUN $SC_PIP install \
      -r tmp/sidecar/requirements/_base.txt


# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/sidecar [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache


COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/sidecar /build/services/sidecar
COPY --chown=scu:scu services/storage/client-sdk /build/services/storage/client-sdk

WORKDIR /build/services/sidecar


RUN $SC_PIP install -r requirements/prod.txt &&\
    $SC_PIP list -v



# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/sidecar [scu:scu]
#
FROM cache as production


ENV SC_BUILD_TARGET production
ENV SC_BOOT_MODE production

WORKDIR /home/scu

RUN mkdir -p services/sidecar &&\
    chown scu:scu services/sidecar &&\
    mv /build/services/sidecar/docker services/sidecar/docker &&\
    rm -rf /build

RUN apk del --no-cache\
      gcc


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

ENV SC_BUILD_TARGET development
ENV SC_BOOT_MODE development


#  TODO: consider installing tooling in a separate virtualenv?
#  TODO: really necesary???
WORKDIR /build


WORKDIR /devel
VOLUME  /devel/packages
VOLUME  /devel/services/sidecar/

ENTRYPOINT [ "/bin/sh", "services/sidecar/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/sidecar/docker/boot.sh"]
