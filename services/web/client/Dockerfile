FROM node:8.9.2 as base-stage

LABEL maintainer=pcrespov

# TODO:  set as host user, otherwise outdir is set as root in the host

ENV NPM_CONFIG_LOGLEVEL warn
ENV PATH="/home/node/qooxdoo-sdk/tool/bin:/home/node/node_modules/.bin/:${PATH}"

#
# + /home/node/            $HOME
#    + client/             $WORKDIR
#       - compile.json
#       + contrib/
#       - contrib.json
#    + node_modules/
#    - package-lock.json
#    - package.json
#    + qooxdoo-sdk
#

# (1) Installs qooxdoo compiler and shallow clone SDK in #HOME. see https://www.npmjs.com/package/qxcompiler
WORKDIR /home/node

COPY package*.json ./

# FIXME: npm WARN node description, ...
# FIXME: npm WARN notice [SECURITY] tunnel-agen
# FIXME: npm WARN notice [SECURITY] hoek
RUN npm i npm@latest && \
    npm install && \
    git clone --depth 1 https://github.com/qooxdoo/qooxdoo.git qooxdoo-sdk

WORKDIR /home/node/client
COPY scripts scripts
RUN chmod +x scripts/*.sh

# ------------------------------------------------------------------------------------------
FROM base-stage as development

# NOTE: cannot expose contrib and source-output volumes (to keep them inside)
# within container does not work well because links remain in host
VOLUME /home/node/client

ENTRYPOINT ./scripts/entrypoint.sh


# ------------------------------------------------------------------------------------------
FROM base-stage as production

# (2) Installs qooxdoo contributions in $WORKDIR/contrib/ within container
COPY compile.json compile.json

RUN ./scripts/install-contrib.sh

# (3) compiles source
COPY source source
COPY Manifest.json Manifest.json

RUN qx compile --target=build

# production exec
VOLUME /home/node/client
EXPOSE 8080

CMD ["qx", "serve"]
