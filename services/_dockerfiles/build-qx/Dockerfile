FROM node:8.9.2

LABEL maintainer=pcrespov

ENV NPM_CONFIG_LOGLEVEL warn

# TODO PC: set as host user, otherwise outdir is set as root in the host
WORKDIR /home/node/

# https://www.npmjs.com/package/qxcompiler
RUN npm install qxcompiler

ENV PATH="/home/node/node_modules/.bin/:${PATH}"

VOLUME /home/node/qxapp
WORKDIR /home/node/qxapp

ENTRYPOINT [ "qx", "compile", "--watch" ]
