# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG DOCKER_REGISTRY="itisfoundation"
ARG BASE_TAG="latest"

# -------------------------- Base stage -------------------
# Shared minimal runtime (see services/_base_images/Dockerfile) + docker-cli + efs user
#
FROM ${DOCKER_REGISTRY}/simcore-runtime-base:${BASE_TAG} AS base
#
#  USAGE:
#     cd services/efs-guardian
#     docker build -f Dockerfile -t efs-guardian:prod --target production ../../
#     docker run efs-guardian:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

# NOTE: to list the latest version run `make` inside `scripts/apt-packages-versions`
ENV DOCKER_APT_VERSION="5:26.1.4-1~debian.12~bookworm"

# Installs the docker CLI (only the cli is needed) on top of the shared runtime base
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  && mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  docker-ce-cli=${DOCKER_APT_VERSION} \
  && apt-get remove -y \
  gnupg \
  curl \
  lsb-release \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  # verify that the binary works
  && gosu nobody true

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
# simcore-efs-user uid=8006(efs) gid=8006(efs) groups=8006(efs)
# Currently all simcore services run as user 8004. The Guardian needs to run as a different user 8006.
# The Guardian has access to the root directory of the EFS distributed file system
# and can change the file permissions of user 8004 if needed.
ENV EFS_USER_ID=8006 \
  EFS_USER_NAME=efs

RUN adduser \
  --uid 8006 \
  --disabled-password \
  --gecos "" \
  --shell /bin/sh \
  --home /home/efs \
  efs

# we create efs-group which is then used in efs guardian when he is creating a directory for user services.
RUN groupadd -g 8106 efs-group
RUN usermod -a -G efs-group efs
RUN usermod -a -G efs-group scu

# Turns off writing .pyc files; superfluous on an ephemeral container.
# NOTE: efs-guardian runs as the `efs` user, the virtualenv lives in its home
ENV VIRTUAL_ENV=/home/efs/.venv
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

EXPOSE 8000
EXPOSE 3000


# -------------------------- Build stage -------------------
# Shared build toolchain + empty virtualenv (see services/_base_images/Dockerfile)
# NOTE: efs-guardian uses a dedicated virtualenv at /home/efs/.venv
#
FROM ${DOCKER_REGISTRY}/simcore-build-base:${BASE_TAG} AS build

ENV VIRTUAL_ENV=/home/efs/.venv
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

# python virtualenv is created in the efs user home so it can be copied to production
RUN mkdir -p /home/efs \
  && uv venv "${VIRTUAL_ENV}"


# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/efs-guardian [scu:scu] WORKDIR
#
FROM build AS prod-only-deps

ENV SC_BUILD_TARGET=prod-only-deps
# https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

WORKDIR /build/services/efs-guardian

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/efs-guardian,target=/build/services/efs-guardian,rw \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip sync \
  requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as efs (non-root user)
#
#  + /home/efs     $HOME = WORKDIR
#    + services/efs-guardian
#
FROM base AS production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/efs

# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --from=prod-only-deps  ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copies booting scripts
COPY services/efs-guardian/docker services/efs-guardian/docker
RUN chmod +x services/efs-guardian/docker/*.sh

# Copies healthcheck script for fast execution (python3 -S skips site-packages)
COPY scripts/docker/docker_healthcheck.py \
  docker/healthcheck.py

# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=120s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "-S", "docker/healthcheck.py", "http://localhost:8000/"]

ENTRYPOINT [ "/bin/sh", "services/efs-guardian/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/efs-guardian/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as "scu" with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build AS development

ENV SC_BUILD_TARGET=development \
  SC_DEVEL_MOUNT=/devel/services/efs-guardian

WORKDIR /devel

RUN chown -R root:root "${VIRTUAL_ENV}"

ENTRYPOINT ["/bin/sh", "services/efs-guardian/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/efs-guardian/docker/boot.sh"]
