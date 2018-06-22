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
# TODO: try installing in venv in $HOME would allow installing as non-root all 3rd, 2nd
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
  libc-dev


ENV HOME /home/scu
ENV SIMCORE_WEB_OUTDIR $HOME/client
ENV PYTHONPATH "$HOME/server/src:$HOME/packages/simcore-sdk/src:$HOME/packages/s3wrapper/src"

WORKDIR /home/scu

# 1. install common 3rd party packages
COPY --chown=scu:scu services/web/server/requirements requirements
RUN pip3 install --no-cache-dir -r requirements/common.txt

EXPOSE 8080

ENTRYPOINT ["python", \
  "-m", "aiohttp.web"]

# ------------------------------------------------------------------------------------------
FROM base-stage as development

ENV SIMCORE_WEB_CONFIG development

# 1.1 install devel 3rd party packages
RUN pip3 install --no-cache-dir -r requirements/devel.txt && \
    rm -rf requirements

USER scu

# 2. creates mounted volumes
RUN mkdir $HOME/client && \
    mkdir $HOME/packages

WORKDIR $HOME/server/src

VOLUME /home/scu/server/
VOLUME /home/scu/client/
VOLUME /home/scu/packages

CMD ["-H", "0.0.0.0", \
     "-P", "8080", \
     "server:create_app"]


# ------------------------------------------------------------------------------------------
FROM base-stage as ci

ENV SIMCORE_WEB_CONFIG production

# 1.1 install devel 3rd party packages
RUN pip3 install --no-cache-dir -r requirements/prod.txt && \
    rm -rf requirements

# 2. install 2nd party packages
COPY --chown=scu:scu packages packages

# 3. install client
COPY --from=services_webclient:build --chown=scu:scu /home/scu/client/build-output client

# 4. install server
COPY --chown=scu:scu services/web/server/src   server/src
COPY --chown=scu:scu services/web/server/tests server/tests

USER scu

WORKDIR $HOME/server/src


CMD ["-H", "0.0.0.0", \
     "-P", "8080", \
     "server:create_app"]


# ------------------------------------------------------------------------------------------
FROM ci as production

RUN rm -rf server/tests
