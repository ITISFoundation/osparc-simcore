# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.11.9"
FROM python:${PYTHON_VERSION}-slim-bookworm as base

#
#  USAGE:
#     cd sercices/efs-guardian
#     docker build -f Dockerfile -t efs-guardian:prod --target production ../../
#     docker run efs-guardian:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=sanderegg

# NOTE: to list the latest version run `make` inside `scripts/apt-packages-versions`
ENV DOCKER_APT_VERSION="5:26.1.4-1~debian.12~bookworm"

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
  gosu \
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
  # only the cli is needed and we remove the unnecessary stuff again
  docker-ce-cli=${DOCKER_APT_VERSION} \
  && apt-get remove -y\
  gnupg \
  curl \
  lsb-release \
  && apt-get clean -y\
  # verify that the binary works
  && gosu nobody true

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
# simcore-efs-user uid=8006(efs) gid=8006(efs) groups=8006(efs)
# Currently all simcore services run as user 8004. The Guardian needs to run as a different user 8006.
# The Guardian has access to the root directory of the EFS distributed file system
# and can change the file permissions of user 8004 if needed.
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  EFS_USER_ID=8006 \
  EFS_USER_NAME=efs \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN adduser \
  --uid 8004 \
  --disabled-password \
  --gecos "" \
  --shell /bin/sh \
  --home /home/scu \
  scu

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

# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8

# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/efs/.venv

# Ensures that the python and pip executables used in the image will be
# those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

EXPOSE 8000
EXPOSE 3000

# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM base as build

ENV SC_BUILD_TARGET=build

RUN --mount=type=cache,target=/var/cache/apt,mode=0755,sharing=private \
  --mount=type=cache,target=/var/lib/apt,mode=0755,sharing=private \
  set -eux \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential

# NOTE: install https://github.com/astral-sh/uv ultra-fast rust-based pip replacement
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install uv~=0.2

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}"

RUN --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install --upgrade  \
  pip~=24.0  \
  wheel \
  setuptools

WORKDIR /build

# install base 3rd party dependencies
# NOTE: copies to /build to avoid overwriting later which would invalidate this layer
RUN \
  --mount=type=bind,source=services/efs-guardian/requirements/_base.txt,target=_base.txt \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement _base.txt


# --------------------------Prod-depends-only stage -------------------
# This stage is for production only dependencies that get partially wiped out afterwards (final docker image concerns)
#
#  + /build
#    + services/efs-guardian [scu:scu] WORKDIR
#
FROM build as prod-only-deps

ENV SC_BUILD_TARGET prod-only-deps

WORKDIR /build/services/efs-guardian

RUN \
  --mount=type=bind,source=packages,target=/build/packages,rw \
  --mount=type=bind,source=services/efs-guardian,target=/build/services/efs-guardian,rw \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  uv pip install \
  --requirement requirements/prod.txt \
  && uv pip list


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/efs-guardian [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/efs
# ensure home folder is read/writable for user efs
RUN chown -R efs /home/efs

# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --chown=efs:efs --from=prod-only-deps  ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copies booting scripts
COPY --chown=efs:efs services/efs-guardian/docker services/efs-guardian/docker
RUN chmod +x services/efs-guardian/docker/*.sh


HEALTHCHECK --interval=10s \
  --timeout=5s \
  --start-period=30s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "services/efs-guardian/docker/healthcheck.py", "http://localhost:8000/"]

ENTRYPOINT [ "/bin/sh", "services/efs-guardian/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/efs-guardian/docker/boot.sh"]


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
  SC_DEVEL_MOUNT=/devel/services/efs-guardian

WORKDIR /devel

RUN chown -R efs:efs "${VIRTUAL_ENV}"

ENTRYPOINT ["/bin/sh", "services/efs-guardian/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/efs-guardian/docker/boot.sh"]
