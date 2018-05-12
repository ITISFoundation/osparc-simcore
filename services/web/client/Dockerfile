FROM node:8.9.2

LABEL maintainer=pcrespov

ENV NPM_CONFIG_LOGLEVEL warn

# TODO PC: set as host user, otherwise outdir is set as root in the host
WORKDIR /home/node/

# https://www.npmjs.com/package/qxcompiler
COPY package*.json ./

ENV PATH="/home/node/qooxdoo-sdk/tool/bin:/home/node/node_modules/.bin/:${PATH}"

RUN npm i npm@latest && \
  npm install && \
  git clone --depth 1 https://github.com/qooxdoo/qooxdoo.git qooxdoo-sdk


VOLUME /home/node/src
WORKDIR /home/node/src

# Add dark theme to web-client
ENTRYPOINT qx contrib update && \
           qx contrib list && \
           qx contrib install ITISFoundation/qx-osparc-theme && \
           qx contrib install ITISFoundation/qx-iconfont-material && \
           qx contrib install ITISFoundation/qx-iconfont-fontawesome5 && \
           qx compile --watch
