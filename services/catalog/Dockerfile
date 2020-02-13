FROM python:3.6-alpine as base
#
#  USAGE:
#     cd sercices/catalog
#     docker build -f Dockerfile -t catalog:prod --target production ../../
#     docker run catalog:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=pcrespov

RUN adduser -D -u 8004 -s /bin/sh -h /home/scu scu

RUN apk add --no-cache \
      su-exec

ENV PATH "/home/scu/.local/bin:$PATH"

# All SC_ variables are customized
ENV SC_PIP pip3 --no-cache-dir
ENV SC_BUILD_TARGET base

EXPOSE 8000


# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#


FROM base as build

ENV SC_BUILD_TARGET build


RUN apk add --no-cache \
      alpine-sdk \
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
COPY  services/catalog/requirements/*.txt \
      services/catalog/requirements/

RUN $SC_PIP install \
      -r services/catalog/requirements/_base.txt


# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/catalog [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache

COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/catalog /build/services/catalog

WORKDIR /build/services/catalog


RUN $SC_PIP install . &&\
    $SC_PIP list -v


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/catalog [scu:scu]
#
FROM cache as production

ENV SC_BUILD_TARGET production
ENV SC_BOOT_MODE production

WORKDIR /home/scu

RUN mkdir -p services/catalog &&\
    chown scu:scu services/catalog &&\
    mv /build/services/catalog/docker services/catalog/docker &&\
    rm -rf /build


RUN apk del --no-cache\
      alpine-sdk \
      alpine-sdk \
      python3-dev \
      musl-dev \
      postgresql-dev

HEALTHCHECK --interval=30s \
            --timeout=20s \
            --start-period=30s \
            --retries=3 \
            CMD ["python3", "services/catalog/docker/healthcheck.py", "http://localhost:8000/v0/"]

ENTRYPOINT [ "/bin/sh", "services/catalog/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/catalog/docker/boot.sh"]


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
VOLUME  /devel/services/catalog/

ENTRYPOINT ["/bin/sh", "services/catalog/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/catalog/docker/boot.sh"]
