#
# Compiles client's source code within an image based in qooxdoo-kit
#
# Note: context at osparc-simcore root folder expected
#
ARG QOOXDOO_KIT_TAG
FROM itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG} as touch

WORKDIR /project
ENV PATH=/home/node/node_modules/.bin:${PATH}

RUN mkdir /project/build-output

FROM touch as build-client

# Installs contributions
COPY --chown=node:node services/static-webserver/client/compile.json compile.json
COPY --chown=node:node services/static-webserver/client/qx-lock.json qx-lock.json
COPY --chown=node:node services/static-webserver/client/Manifest.json Manifest.json

# Install packages (warning: cache might keep these library out-of-date!)
# TODO: should we freeze packages??
RUN qx package update &&\
  qx package install &&\
  ls -la qx_packages
# -> /project/qx_packages


# Copy sources and compile inside the image
COPY --chown=node:node services/static-webserver/client/source source
COPY --chown=node:node services/static-webserver/client/Manifest.json Manifest.json

ARG VCS_URL=undefined
ARG VCS_REF="undefined"
ARG VCS_REF_CLIENT=undefined
ARG VCS_STATUS_CLIENT=undefined

RUN qx compile --target=build \
  --set-env osparc.vcsOriginUrl="${VCS_URL}" \
  --set-env osparc.vcsRef="${VCS_REF}" \
  --set-env osparc.vcsRefClient="${VCS_REF_CLIENT}" \
  --set-env osparc.vcsStatusClient="${VCS_STATUS_CLIENT}" && \
  ls -la build-output
# -> /project/build-output

# ------------------------------ STATIC WEB SERVER ----------------------
FROM joseluisq/static-web-server:1.16.0-alpine as base

LABEL maintainer=neagu@itis.swiss

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN adduser -D -u ${SC_USER_ID} -s /bin/sh -h /home/${SC_USER_NAME} ${SC_USER_NAME}


# changing ownership of static-web-server files
RUN chown -R ${SC_USER_NAME}:${SC_USER_NAME} /entrypoint.sh
RUN chown -R ${SC_USER_NAME}:${SC_USER_NAME} /usr/local/bin/static-web-server
RUN chown -R ${SC_USER_NAME}:${SC_USER_NAME} /public

USER ${SC_USER_NAME}

FROM base as build
ENV SC_BUILD_TARGET build

FROM base as production
ENV SC_BUILD_TARGET production
# front-end client last (image name is the path to the Dockerfile)
COPY --from=build-client --chown=${SC_USER_NAME}:${SC_USER_NAME} \
  /project/build-output /static-content


FROM base as development
ENV SC_BUILD_TARGET development
