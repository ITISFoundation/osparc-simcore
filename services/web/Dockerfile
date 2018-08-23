FROM python:3.6-alpine as base-stage

LABEL maintainer=pcrespov

#  USAGE:
#     docker build -f Dockerfile -t web:ci --target ci ../../
#     docker run web:ci
#
#  REQUIRED: context expected at $(this-file-dir)/../../
#  REQUIRED: client_qx:build image ready

#
# + /home/scu/              $HOME
#    + client               $SIMCORE_WEB_OUTDIR
#       - index.html
#        ...
#    + packages         *   installed simcore/packages
#       + simcore_sdk
#    + server
#       + src           *
#       + tests
#
#  * = in PYTHONPATH
#
#
# TODO: try installing in .venv in $HOME would allow installing as non-root all 3rd, 2nd
#       and even the application itself
#
# TODO: straight copying python packages bring unnecessary files (e.g. __pycache__) -> dockerignore!
#       could copy and then python setup.py install OR git clone into the container.
#       This applies for both
#

RUN adduser -D -u 8004 scu

RUN apk add --no-cache \
  postgresql-dev \
  gcc \
  libc-dev \
  libffi-dev


ENV HOME /home/scu
ENV SIMCORE_WEB_OUTDIR $HOME/client
#ENV SIMCORE_WEB_OUTDIR $HOME/src/static
ENV IS_CONTAINER_CONTEXT Yes
ENV PYTHONPATH "$HOME/server/src:$HOME/packages/simcore-sdk/src:$HOME/packages/s3wrapper/src"


WORKDIR /home/scu

# 1. install base 3rd party packages
COPY --chown=scu:scu services/web/server/requirements requirements
RUN pip3 install --no-cache-dir -r requirements/base.txt

EXPOSE 8080

ENTRYPOINT ["python3", "-m", "aiohttp.web"]

# ------------------------------------------------------------------------------------------
FROM base-stage as development

ENV SIMCORE_WEB_CONFIG development

# 1.1 install packages needed for testing
RUN pip3 install --no-cache-dir -r requirements/tests.txt && \
    rm -rf requirements

USER scu

# 2. creates mounted volumes
RUN mkdir $HOME/client && \
    mkdir $HOME/packages

WORKDIR $HOME/server/src

VOLUME /home/scu/server/
VOLUME /home/scu/client/
VOLUME /home/scu/packages

# TODO: add watch functionality in dev mode
CMD ["-H", "0.0.0.0", \
     "-P", "8080", \
     "server.main:init_app"]


# ------------------------------------------------------------------------------------------
FROM base-stage as production

ENV SIMCORE_WEB_CONFIG production

# 2. install 2nd party packages
COPY --chown=scu:scu packages packages

# 3. install client
COPY --from=services_webclient:build --chown=scu:scu /home/scu/client/build-output client

# 4. install server
COPY --chown=scu:scu services/web/server/src server/src

USER scu

WORKDIR $HOME/server/src

CMD ["-H", "0.0.0.0", \
     "-P", "8080", \
     "server.main:init_app"]


# ------------------------------------------------------------------------------------------
FROM base-stage as ci

ENV SIMCORE_WEB_CONFIG production

# 2. install 2nd party packages
COPY --chown=scu:scu packages packages

# 3. install client
COPY --from=services_webclient:build --chown=scu:scu /home/scu/client/build-output client

# 4. copy all server
COPY --chown=scu:scu services/web/server server

WORKDIR $HOME/server/

# 5. installs all packages
RUN pip3 install --no-cache-dir -r requirements/docker-ci.txt

USER scu

WORKDIR $HOME/server/src

CMD ["-H", "0.0.0.0", \
     "-P", "8080", \
     "server.main:init_app"]
