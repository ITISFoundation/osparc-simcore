ARG PYTHON_VERSION="3.6.10"
FROM python:${PYTHON_VERSION}-slim-buster as base
#
#  USAGE:
#     cd sercices/storage
#     docker build -f Dockerfile -t storage:prod --target production ../../
#     docker run storage:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer=mguidon

RUN set -eux; \
  apt-get update; \
  apt-get install -y gosu; \
  rm -rf /var/lib/apt/lists/*; \
  # verify that the binary works
  gosu nobody true


# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN adduser \
  --uid ${SC_USER_ID} \
  --disabled-password \
  --gecos "" \
  --shell /bin/sh \
  --home /home/${SC_USER_NAME} \
  ${SC_USER_NAME}


# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8

# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv

# Ensures that the python and pip executables used
# in the image will be those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"


ENV SC_BUILD_TARGET base
ENV SC_BOOT_MODE default

EXPOSE 8080
# -------------------------- -------------------------------



# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#

FROM base as build

ENV SC_BUILD_TARGET build

RUN apt-get update &&\
  apt-get install -y --no-install-recommends \
  build-essential


# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN python -m venv ${VIRTUAL_ENV}

RUN pip --no-cache-dir install --upgrade \
  pip~=20.1.1  \
  wheel \
  setuptools

WORKDIR /build

# install only base 3rd party dependencies
COPY  --chown=scu:scu services/storage/requirements/_base.txt requirements_base.txt
RUN pip --no-cache-dir --quiet install -r requirements_base.txt
# -------------------------- -------------------------------




# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/storage [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache

# 2nd party packages
COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/storage /build/services/storage

WORKDIR /build/services/storage

RUN pip --no-cache-dir --quiet install -r requirements/prod.txt
# -------------------------- -------------------------------



# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
#
FROM base as production

ENV SC_BUILD_TARGET=production \
  SC_BOOT_MODE=production \
  SC_HEALTHCHECK_INTERVAL=30 \
  SC_HEALTHCHECK_RETRY=3

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# bring installed package without build tools
COPY --from=cache --chown=scu:scu ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# copy docker entrypoint and boot scripts
COPY --chown=scu:scu services/storage/docker services/storage/docker
RUN chmod +x services/storage/docker/*.sh

HEALTHCHECK --interval=30s \
  --timeout=120s \
  --start-period=30s \
  --retries=3 \
  CMD ["python3", "/home/scu/services/storage/docker/healthcheck.py", "http://localhost:8080/v0/"]


ENTRYPOINT [ "/bin/sh", "services/storage/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/storage/docker/boot.sh"]
# -------------------------- -------------------------------




# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as scu with same gid/uid as host
#
#  + /devel         WORKDIR
#    + packages  (mounted volume)
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET=development \
  SC_DEVEL_MOUNT=/devel/services/storage/


RUN chown -R scu:scu ${VIRTUAL_ENV}

# NOTE: declaring VOLUMEs here makes troubles mounting
#       the client's output folder to /devel/services/web/client.
#       The latter ls no files

ENTRYPOINT [ "/bin/sh", "services/storage/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/storage/docker/boot.sh"]
# -------------------------- -------------------------------
