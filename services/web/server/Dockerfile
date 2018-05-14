FROM node:8.9.2 as qx-stage
#FIXME: FROM itisfoundation/qooxdoo-compiler:latest as qx-stage

ARG client_dir=web/client

# workdir
WORKDIR /home/node/src
RUN chown -R node:node /home/node/src

# user defined in base image
USER node

# npm variables
ENV NPM_CONFIG_LOGLEVEL=warn
ENV NPM_CONFIG_PREFIX=/home/node/.npm-global
ENV QOOXDOO_COMPILER_DIR=$NPM_CONFIG_PREFIX/lib/node_modules/qxcompiler
ENV PATH=$NPM_CONFIG_PREFIX/bin:$PATH

RUN npm install -g qxcompiler

# client's source code TODO: move everything under webapp
COPY --chown=node:node $client_dir/source source
COPY --chown=node:node $client_dir/compile.json compile.json
COPY --chown=node:node $client_dir/Manifest.json Manifest.json

RUN ln -s $QOOXDOO_COMPILER_DIR/node_modules /home/node

# Add dark theme to web/client
RUN qx contrib update && qx contrib list
RUN qx contrib install ITISFoundation/qx-osparc-theme
RUN qx compile

# -------------------------common-py-stage------------------------------------
FROM python:3.6-alpine as common-py-stage

#
# + /usr/src
#    + /requirements
#    + /test
#    + /source        <-- web/server/source (pwd)
#        + /client    <-- web/client/source-output

# TODO: create non-root user

ARG server_dir=web/server

WORKDIR /usr/src/source

ENV SIMCORE_WEB_OUTDIR=$PWD/client
ENV DIRECTOR_HOST='director'
ENV DIRECTOR_PORT=8001

# client compiled code
COPY --from=qx-stage /home/node/src/source-output ${SIMCORE_WEB_OUTDIR}

# packages
COPY $server_dir/requirements/common.txt /usr/src/requirements/common.txt
RUN pip3 install --no-cache-dir -r /usr/src/requirements/common.txt

EXPOSE 8080


# ----------------------------development---------------------------------
FROM common-py-stage as development

ARG server_dir=web/server

ENV SIMCORE_WEB_CONFIG=development

COPY $server_dir/requirements/dev.txt /usr/src/requirements/dev.txt
RUN pip3 install --no-cache-dir -r /usr/src/requirements/dev.txt \
  && python --version \
  && pip list --format=columns \
  && echo \
  && ls -l $PWD

CMD ["python", "-m", "aiohttp.web", "-H", "0.0.0.0", "-P", "8080", "server:create_app"]



# -----------------------------production--------------------------------
FROM common-py-stage as production

ARG server_dir=web/server

ENV SIMCORE_WEB_CONFIG=production

COPY $server_dir/requirements/prod.txt /usr/src/requirements/prod.txt
RUN pip3 install --no-cache-dir -r /usr/src/requirements/prod.txt \
    && python --version \
    && pip list --format=columns

COPY $server_dir/source .

ENTRYPOINT ["python", "-m", "aiohttp.web"]

CMD ["-H", "0.0.0.0", "-P", "8080", "server:create_app"]
