# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.10"
FROM itisfoundation/osparc-base-python:${PYTHON_VERSION} as base

#
#  USAGE:
#     cd sercices/director-v2
#     docker build -f Dockerfile -t director-v2 :prod --target production ../../
#     docker run director-v2 :prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=pcrespov
EXPOSE 8000
EXPOSE 3000

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM itisfoundation/osparc-builder-python:${PYTHON_VERSION} as build

# install base 3rd party dependencies
RUN \
  --mount=type=bind,source=services/director-v2/requirements/_base.txt,target=_base.txt \
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  --requirement _base.txt


# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/director-v2 [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET prod-only-deps

WORKDIR /build/services/director-v2

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/director-v2,target=/build/services/director-v2,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install \
  --requirement requirements/prod.txt \
  && pip list -v


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/director-v2 [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --chown=scu:scu --from=prod-only-deps  ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copies booting scripts
COPY --chown=scu:scu services/director-v2/docker services/director-v2/docker
RUN chmod +x services/director-v2/docker/*.sh


HEALTHCHECK --interval=30s \
  --timeout=20s \
  --start-period=30s \
  --retries=3 \
  CMD ["python3", "services/director-v2/docker/healthcheck.py", "http://localhost:8000/"]

ENTRYPOINT [ "/bin/sh", "services/director-v2/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/director-v2/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as myu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET=development \
  SC_DEVEL_MOUNT=/devel/services/director-v2

WORKDIR /devel

RUN chown -R scu:scu "${VIRTUAL_ENV}"

ENTRYPOINT ["/bin/sh", "services/director-v2/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/director-v2/docker/boot.sh"]
