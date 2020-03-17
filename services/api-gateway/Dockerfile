FROM python:3.8.1-alpine3.11 as base
#
#  USAGE:
#     cd sercices/api-gateway
#     docker build -f Dockerfile -t api-gateway:prod --target production ../../
#     docker run api-gateway:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages


LABEL maintainer=pcrespov

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
RUN adduser -D -u 8004 -s /bin/sh -h /home/scu scu

RUN apk add --no-cache \
      su-exec

ENV PATH "/home/scu/.local/bin:$PATH"

# NOTE: All SC_ variables are customized
ENV SC_PIP pip3 --no-cache-dir
ENV SC_BUILD_TARGET base

EXPOSE 8000
EXPOSE 3000

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM base as build

ENV SC_BUILD_TARGET build

RUN apk add --no-cache \
      alpine-sdk \
      python3-dev \
      musl-dev \
      postgresql-dev

RUN $SC_PIP install --upgrade \
      pip \
      wheel \
      setuptools

WORKDIR /build

# install base 3rd party dependencies
COPY  services/api-gateway/requirements/*.txt \
      services/api-gateway/requirements/

RUN $SC_PIP install \
      -r services/api-gateway/requirements/_base.txt


# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/api-gateway [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache


COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/api-gateway /build/services/api-gateway

WORKDIR /build/services/api-gateway


RUN $SC_PIP install . &&\
    $SC_PIP list -v


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/api-gateway [scu:scu]
#
FROM cache as production

ENV SC_BUILD_TARGET production
ENV SC_BOOT_MODE production

WORKDIR /home/scu

RUN mkdir -p services/api-gateway &&\
    chown scu:scu services/api-gateway &&\
    mv /build/services/api-gateway/docker services/api-gateway/docker &&\
    rm -rf /build


RUN apk del --no-cache\
      alpine-sdk \
      python3-dev \
      musl-dev \
      postgresql-dev


HEALTHCHECK --interval=30s \
            --timeout=20s \
            --start-period=30s \
            --retries=3 \
            CMD ["python3", "services/api-gateway/docker/healthcheck.py", "http://localhost:8000/"]

ENTRYPOINT [ "/bin/sh", "services/api-gateway/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/api-gateway/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as myu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET development
ENV SC_BOOT_MODE development



WORKDIR /build

WORKDIR /devel
VOLUME  /devel/packages
VOLUME  /devel/services/api-gateway/

ENTRYPOINT ["/bin/sh", "services/api-gateway/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/api-gateway/docker/boot.sh"]
