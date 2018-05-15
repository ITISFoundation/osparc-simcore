FROM node:8.9.2 AS common
ENV NPM_CONFIG_LOGLEVEL warn
# + /home/node/
#    + app/source-output/
#    + app/source/
#    + app/*.json

WORKDIR /home/node/
RUN npm install qxcompiler

ENV PATH="/home/node/node_modules/.bin/:${PATH}"

WORKDIR /home/node/qxapp

#-----------------Development-----------------------
FROM common as development

CMD ["qx", "compile", "--watch"]

#-----------------Production----------------------
FROM common AS production

COPY  source /home/node/qxapp/source
COPY *.json ./
RUN qx compile --target=build