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
FROM python:3 as common-py-stage

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
COPY $server_dir/requirements/common.txt requirements/common.txt
RUN pip3 install --no-cache-dir -r requirements/common.txt

RUN python --version \
 && pip list --format=columns

EXPOSE 8080

# -------------------------------------------------------------
FROM common-py-stage as development

ARG server_dir=web-server

COPY $server_dir/requirements/dev.txt requirements/dev.txt
RUN pip3 install --no-cache-dir -r requirements/dev.txt

EXPOSE 9081
EXPOSE 9082

CMD ["python", "-m", "aiohttp.web -H ${SIMCORE_WEB_HOSTNAME} -P ${SIMCORE_WEB_PORT} server:create_app"]


# -------------------------------------------------------------
FROM common-py-stage as production

ARG server_dir=web-server

COPY $server_dir/requirements/prod.txt requirements/prod.txt
RUN pip3 install --no-cache-dir -r requirements/prod.txt

COPY $server_dir/source ./

# TODO: why not directly python?
ENTRYPOINT ["sh", "-c", "python -m aiohttp.web -H ${SIMCORE_WEB_HOSTNAME} -P ${SIMCORE_WEB_PORT} server:create_app"]
