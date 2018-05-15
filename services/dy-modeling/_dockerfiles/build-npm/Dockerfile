FROM node:8.9.2

ENV NPM_CONFIG_LOGLEVEL warn

# Web server variables
ARG web_app_port=8080
ENV SIMCORE_WEB_HOSTNAME "0.0.0.0"
ENV SIMCORE_WEB_PORT $web_app_port
ENV SIMCORE_WEB_OUTDIR /home/node/source-output

# S4L as CompServ variables
ARG s4l_ip="0.0.0.0"
ARG s4l_port_app="9095"
ARG s4l_port_mod="9096"
ENV CS_S4L_HOSTNAME $s4l_ip
ENV CS_S4L_PORT_APP $s4l_port_app
ENV CS_S4L_PORT_MOD $s4l_port_mod

WORKDIR /home/node/
VOLUME /home/node/source-output
VOLUME /home/node

EXPOSE $web_app_port

# TODO ensure npm@5.5.1
ENTRYPOINT npm install -y \
  && echo node $(node --version) \
  && echo npm $(npm --version) \
  && npm install promise \
  && npm install nodemon -g \
  && nodemon -L start