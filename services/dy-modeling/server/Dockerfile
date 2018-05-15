FROM node:8.9.2 AS common

ENV NPM_CONFIG_LOGLEVEL warn

# Web server variables
ARG web_app_port=8080
ENV SIMCORE_WEB_HOSTNAME "0.0.0.0"
ENV SIMCORE_WEB_PORT $web_app_port
ENV SIMCORE_WEB_OUTDIR /home/node/source-output
EXPOSE $web_app_port
LABEL simcore.service.settings='[{"name": "ports", "type": "int", "value": 9090}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}, {"name": "env", "type": "string", "value": ["CS_S4L_HOSTNAME=xrpc-worker_%service_uuid%"]}]'

# S4L host and ports
ARG s4l_ip="0.0.0.0"
ARG s4l_port_app="9095"
ARG s4l_port_mod="9096"
ENV CS_S4L_HOSTNAME $s4l_ip
ENV CS_S4L_PORT_APP $s4l_port_app
ENV CS_S4L_PORT_MOD $s4l_port_mod

# + /home/node/          json files
#    + source-output/    client source files
#    + source/  server   source files
WORKDIR /home/node/
COPY package.json /home/node/package.json
VOLUME /home/node/source-output
#--------------------Development------------------
FROM common AS development

RUN npm install -y \
  && npm install nodemon -g

CMD ["nodemon", "-L", "start"]

#---------------------Production------------------
FROM common AS production
WORKDIR /home/node/
COPY --from=client-prod:latest /home/node/qxapp/build-output source-output
COPY source /home/node/source
RUN npm install -y

ENTRYPOINT ["npm", "start"]