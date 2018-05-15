# Compilation stage ----
FROM node:8.9.2

LABEL maintainer=pcrespov

ENV NPM_CONFIG_LOGLEVEL warn

WORKDIR /home/node/
# https://www.npmjs.com/package/qxcompiler
RUN npm install qxcompiler

# TODO: why to create again? not better taking entire client??
ENV PATH="/home/node/node_modules/.bin/:${PATH}"
#RUN qx create qxapp -I --qxpath /home/node/node_modules/qooxdoo-sdk/framework/

WORKDIR /home/node/qxapp
COPY client/source source
COPY client/*.json ./
RUN qx compile


# Deployment stage -----
FROM node:8.9.2

# Web server variables
ARG web_app_port=8080
ENV SIMCORE_WEB_HOSTNAME "0.0.0.0"
ENV SIMCORE_WEB_PORT $web_app_port
ENV SIMCORE_WEB_OUTDIR /home/node/source-output
LABEL simcore.service.settings='[{"name": "ports", "type": "int", "value": 9090}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}, {"name": "env", "type": "string", "value": ["CS_S4L_HOSTNAME=xrpc-worker_%service_uuid%"]}]'

# S4L as CompServ variables
ARG s4l_ip="0.0.0.0"
ARG s4l_port_app="9095"
ARG s4l_port_mod="9096"
ENV CS_S4L_HOSTNAME $s4l_ip
ENV CS_S4L_PORT_APP $s4l_port_app
ENV CS_S4L_PORT_MOD $s4l_port_mod

WORKDIR /home/node/
COPY --from=0 /home/node/qxapp/source-output source-output
COPY server .

# TODO ensure npm@5.5.1
RUN npm install -y \
  && npm install promise \
  && echo node $(node --version) \
  && echo npm $(npm --version)

EXPOSE $web_app_port

CMD ["npm", "start"]
