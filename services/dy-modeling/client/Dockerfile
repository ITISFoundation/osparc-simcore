FROM node:8.9.2 AS common

LABEL maintainer=pcrespov

ENV NPM_CONFIG_LOGLEVEL warn


# + /home/node/
#    + app/source-output/
#    + app/source/
#    + app/*.json

WORKDIR /home/node/
RUN npm install qxcompiler

ENV PATH="/home/node/node_modules/.bin/:${PATH}"

VOLUME /home/node/app
WORKDIR /home/node/app

#-----------------Development-----------------------
FROM common as development

CMD ["qx", "compile", "--watch"]

#-----------------Production----------------------
FROM common AS production

COPY  --chown=node:node source /home/node/app/source
COPY --chown=node:node *.json ./
RUN qx compile