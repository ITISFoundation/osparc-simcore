#FIXME: FROM itisfoundation/qooxdoo-compiler:latest as qx-stage
FROM node:8.9.2 as qx-stage

ARG client_dir=web-client

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

# Add dark theme to web-client
RUN qx contrib update && qx contrib list
RUN qx contrib install ITISFoundation/qx-osparc-theme
RUN qx compile

# -------------------------------------------------------------
# TODO: use python:3.6-alpine
FROM python:3 as production

ARG server_dir=web-server

WORKDIR /usr/src/app

ENV SIMCORE_WEB_OUTDIR=/usr/src/app/client
ENV SIMCORE_WEB_HOSTNAME='0.0.0.0'
ENV SIMCORE_WEB_PORT=8080
ENV DIRECTOR_HOST='http://director'
ENV DIRECTOR_PORT=8001

# client
COPY --from=qx-stage /home/node/src/source-output client

# packages
COPY $server_dir/requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt
RUN python --version \
    && pip list --format=columns

# server
COPY $server_dir/* ./

EXPOSE 8080

# TODO: why not directly python?
ENTRYPOINT ["sh", "-c", "python -m aiohttp.web -H ${SIMCORE_WEB_HOSTNAME} -P ${SIMCORE_WEB_PORT} server:create_app"]
