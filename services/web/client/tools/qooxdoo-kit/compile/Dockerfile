FROM itisfoundation/qooxdoo-kit:latest as build-client

# Expects context at web/client

WORKDIR /project
ENV PATH=/home/node/node_modules/.bin:${PATH}

# Installs contrib
COPY --chown=node:node compile.json compile.json
COPY --chown=node:node qx-lock.json qx-lock.json
COPY --chown=node:node Manifest.json Manifest.json

RUN qx package update &&\
    qx package install &&\
    ls -la qx_packages
# -> /project/qx_packages


# compiles sources
COPY --chown=node:node source source
COPY --chown=node:node Manifest.json Manifest.json

ARG VCS_URL=undefined
ARG VCS_REF="undefined"
ARG VCS_REF_CLIENT=undefined
ARG VCS_STATUS_CLIENT=undefined

RUN qx compile --target=build \
  --set osparc.vcsOriginUrl="'${VCS_URL}'" \
  --set osparc.vcsRef="'${VCS_REF}'" \
  --set osparc.vcsRefClient="'${VCS_REF_CLIENT}'" \
  --set osparc.vcsStatusClient="'${VCS_STATUS_CLIENT}'" &&\
  ls -la build-output
# -> /project/build-output
