# Compilation stage ----
FROM node:8.9.2

LABEL maintainer=pcrespov

ENV NPM_CONFIG_LOGLEVEL warn

WORKDIR /home/node/
# https://www.npmjs.com/package/qxcompiler
RUN npm install qxcompiler

# TODO: why to create again? not better taking entire client-qx??
ENV PATH="/home/node/node_modules/.bin/:${PATH}"
#RUN qx create qxapp -I --qxpath /home/node/node_modules/qooxdoo-sdk/framework/

VOLUME /home/node/qxapp
WORKDIR /home/node/qxapp


ENTRYPOINT qx compile --watch
