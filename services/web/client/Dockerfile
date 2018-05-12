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

# (2) Installs qooxdoo contributions in $WORKDIR/contrib/ within container
WORKDIR /home/node/client

COPY compile.json compile.json
COPY source/resource/iconfont/create-links-to-contrib.sh source/resource/iconfont/create-links-to-contrib.sh

RUN qx contrib update && \
  qx contrib list && \
  qx contrib install ITISFoundation/qx-osparc-theme && \
  qx contrib install ITISFoundation/qx-iconfont-material && \
  qx contrib install ITISFoundation/qx-iconfont-fontawesome5 && \
  cp contrib.json /home/node/contrib.json && \
  rm compile.json
 
# ------------------------------------------------------------------------------------------
FROM base-stage as development

RUN cd source/resource/iconfont/ && \
  chmod +x create-links-to-contrib.sh && \
  /bin/sh ./create-links-to-contrib.sh

WORKDIR /home/node/client

VOLUME /home/node/client/contrib
VOLUME /home/node/client/source/resource/iconfont
VOLUME /home/node/client

#ENTRYPOINT qx contrib update && \
#  qx contrib list && \
#  qx contrib install ITISFoundation/qx-osparc-theme && \
#  qx contrib install ITISFoundation/qx-iconfont-material && \
#  qx contrib install ITISFoundation/qx-iconfont-fontawesome5 && \
#  qx serve 
#  qx compile --watch
ENTRYPOINT ln -s ../contrib.json contrib.json && \
  qx serve

# ------------------------------------------------------------------------------------------
FROM base-stage as production

WORKDIR /home/node/client

COPY source source
COPY compile.json compile.json
COPY Manifest.json Manifest.json

RUN cd source/resource/iconfont/ && \
  chmod +x create-links-to-contrib.sh && \
  /bin/sh ./create-links-to-contrib.sh && \
  cd $OLD_PWD

RUN qx compile 

CMD ["qx", "serve"]
