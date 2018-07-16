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

# call git rev-parse — short HEAD in a bash
ARG VCS_REF
# call date -u +”%Y-%m-%dT%H:%M:%SZ” in a bash
ARG BUILD_DATE
# Labels.
LABEL org.label-schema.schema-version="1.0" \
    org.label-schema.build-date=${BUILD_DATE} \
    org.label-schema.url="https://www.itis.ethz.ch" \
    org.label-schema.vcs-url="https://github.com/ITISFoundation/osparc-simcore" \
    org.label-schema.vcs-ref=${VCS_REF} \
    org.label-schema.vendor="IT'IS foundation"

#-----------------Development-----------------------
FROM common as development

CMD ["qx", "compile", "--watch"]

#-----------------Production----------------------
FROM common AS production

COPY  source /home/node/qxapp/source
COPY *.json ./
RUN qx compile --target=build