ARG PYTHON_VERSION="3.8.4"
FROM python:${PYTHON_VERSION}-slim-buster as base
#
#  USAGE:
#     cd sercices/scheduler
#     docker build -f Dockerfile -t scheduler:prod --target production ../../
#     docker run scheduler:prod
#
#  REQUIRED: context expected at ``osparc-simcore/`` folder because we need access to osparc-simcore/packages

LABEL maintainer="Andrei Neagu <neagu@itis.swiss>"

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


# -------------------------- Build stage -------------------
# Installs build/package management tools and third party dependencies
#
# + /build             WORKDIR
#
FROM base as build

ENV SC_BUILD_TARGET=build

RUN apt-get update &&\
    apt-get install -y --no-install-recommends \
    build-essential

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN python -m venv ${VIRTUAL_ENV}

RUN pip install --upgrade --no-cache-dir \
    pip~=20.1.1  \
    wheel \
    setuptools

WORKDIR /build

# install base 3rd party dependencies
# NOTE: copies to /build to avoid overwriting later which would invalidate this layer
COPY --chown=scu:scu services/scheduler/requirements/_base.txt .
RUN pip --no-cache-dir install -r _base.txt

# --------------------------Cache stage -------------------
# CI in master buils & pushes this target to speed-up image build
#
#  + /build
#    + services/scheduler [scu:scu] WORKDIR
#
FROM build as cache

ENV SC_BUILD_TARGET cache

COPY --chown=scu:scu packages /build/packages
COPY --chown=scu:scu services/scheduler /build/services/scheduler

WORKDIR /build/services/scheduler

RUN pip --no-cache-dir install -r requirements/prod.txt &&\
    pip --no-cache-dir list -v


# --------------------------Production stage -------------------
# Final cleanup up to reduce image size and startup setup
# Runs as scu (non-root user)
#
#  + /home/scu     $HOME = WORKDIR
#    + services/scheduler [scu:scu]
#
FROM base as production

ENV SC_BUILD_TARGET=production \
    SC_BOOT_MODE=production

ENV PYTHONOPTIMIZE=TRUE

WORKDIR /home/scu

# Starting from clean base image, copies pre-installed virtualenv from cache
COPY --chown=scu:scu --from=cache  ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copies booting scripts
COPY --chown=scu:scu services/scheduler/docker services/scheduler/docker
RUN chmod +x services/scheduler/docker/*.sh

HEALTHCHECK --interval=30s \
    --timeout=20s \
    --start-period=30s \
    --retries=3 \
    CMD ["python3", "services/scheduler/docker/healthcheck.py", "http://localhost:8000/"]

EXPOSE 8000

ENTRYPOINT [ "/bin/sh", "services/scheduler/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/scheduler/docker/boot.sh"]


# --------------------------Development stage -------------------
# Source code accessible in host but runs in container
# Runs as myu with same gid/uid as host
# Placed at the end to speed-up the build if images targeting production
#
#  + /devel         WORKDIR
#    + services  (mounted volume)
#
FROM build as development

ENV SC_BUILD_TARGET=development

WORKDIR /devel

RUN chown -R scu:scu ${VIRTUAL_ENV}

EXPOSE 8000
EXPOSE 3000

ENTRYPOINT ["/bin/sh", "services/scheduler/docker/entrypoint.sh"]
CMD ["/bin/sh", "services/scheduler/docker/boot.sh"]
