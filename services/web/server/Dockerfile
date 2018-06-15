#FIXME: MUST use the same as web/client/Dockerfile
FROM node:8.9.2 as qx-stage
#
# + /home/scu/
#    + /client           =$SIMCORE_WEB_OUTDIR
#    + /server
#       + /requirements
#       + /tests
#       + /src           =$PWD


# client_dir = path to client dir from context
ARG client_dir=web/client

# user defined in base image
USER node

# workdir
WORKDIR /home/node

RUN chown -R node:node /home/node


# npm variables
ENV PATH=/home/node/node_modules/.bin:$PATH

COPY --chown=node:node $client_dir/package*.json .
RUN npm install && \
    git clone --depth=1 https://github.com/qooxdoo/qooxdoo.git qooxdoo-sdk && \
    mkdir src

# workdir
WORKDIR /home/node/src

USER node

COPY --chown=node:node $client_dir/source source
COPY --chown=node:node $client_dir/scripts scripts
COPY --chown=node:node $client_dir/compile.json .
COPY --chown=node:node $client_dir/Manifest.json .

# client's source code TODO: move everything under webapp

RUN ls -l ; ./scripts/install-contrib.sh ; \
    qx compile

# -------------------------common-py-stage------------------------------------
FROM python:3.6-alpine as common-py-stage
#
# + /home/scu/
#    + /client           =$SIMCORE_WEB_OUTDIR
#    + /server
#       + /requirements
#       + /tests
#       + /src           =$PWD


# TODO: create non-root user

ARG server_dir=web/server

RUN apk add --no-cache \
  postgresql-dev \
  gcc \
  libc-dev

WORKDIR /usr/src/source

ENV SIMCORE_WEB_OUTDIR=/usr/src/client
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
RUN pip3 install --no-cache-dir -r /usr/src/requirements/dev.txt
RUN python --version && \
    pip list --format=columns && \
    echo; ls -l $PWD

# TODO: web should re-serve upon changes on code (both client)
CMD ["python", "-m", "aiohttp.web", "-H", "0.0.0.0", "-P", "8080", "server:create_app"]



# -----------------------------production--------------------------------
FROM common-py-stage as production

ARG server_dir=web/server

ENV SIMCORE_WEB_CONFIG=production

COPY $server_dir/requirements/prod.txt /usr/src/requirements/prod.txt
RUN pip3 install --no-cache-dir -r /usr/src/requirements/prod.txt \
    && python --version \
    && pip list --format=columns

COPY $server_dir/src .
COPY packages /usr/src/packages

ENTRYPOINT ["python", "-m", "aiohttp.web"]

CMD ["-H", "0.0.0.0", "-P", "8080", "server:create_app"]
