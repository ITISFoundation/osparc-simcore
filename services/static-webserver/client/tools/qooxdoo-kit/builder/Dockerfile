# syntax=docker/dockerfile:1
#
# Compiles client's source code within an image based in qooxdoo-kit
#
# Note: context at osparc-simcore/services/static-webserver/client expected
#
ARG tag
FROM itisfoundation/qooxdoo-kit:${tag} as touch

WORKDIR /project
ENV PATH=/home/node/node_modules/.bin:${PATH}

RUN mkdir /project/build-output

FROM touch as build-client

# Installs contributions
# Install packages (warning: cache might keep these library out-of-date!)
# TODO: should we freeze packages??
RUN \
  --mount=type=bind,source=compile.json,target=compile.json \
  --mount=type=bind,source=qx-lock.json,target=qx-lock.json \
  --mount=type=bind,source=Manifest.json,target=Manifest.json \
  qx package update &&\
  qx package install &&\
  ls -la qx_packages
# -> /project/qx_packages


# Copy sources and compile inside the image
ARG VCS_URL=undefined
ARG VCS_REF="undefined"
ARG VCS_REF_CLIENT=undefined
ARG VCS_STATUS_CLIENT=undefined

# Increase to 5 GB, this does not fix the probable memory leak but allows to go further
ENV NODE_OPTIONS="--max-old-space-size=5120"

# this nice call prints the actual heap size limit in GB
RUN \
  --mount=type=bind,source=source,target=source \
  --mount=type=bind,source=compile.json,target=compile.json \
  --mount=type=bind,source=qx-lock.json,target=qx-lock.json \
  --mount=type=bind,source=Manifest.json,target=Manifest.json \
  node -e 'console.log(v8.getHeapStatistics().heap_size_limit/(1024*1024))' && \
  qx compile --target=build \
  --set-env osparc.vcsOriginUrl="${VCS_URL}" \
  --set-env osparc.vcsRef="${VCS_REF}" \
  --set-env osparc.vcsRefClient="${VCS_REF_CLIENT}" \
  --set-env osparc.vcsStatusClient="${VCS_STATUS_CLIENT}" && \
  ls -la build-output
# -> /project/build-output


FROM joseluisq/static-web-server:1.16.0-alpine as server-base

LABEL org.opencontainers.image.authors="GitHK, odeimaiz"

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN adduser -D -u ${SC_USER_ID} -s /bin/sh -h /home/${SC_USER_NAME} ${SC_USER_NAME}

# changing ownership of static-web-server files
RUN chown -R "${SC_USER_NAME}:${SC_USER_NAME}" /entrypoint.sh && \
  chown -R "${SC_USER_NAME}:${SC_USER_NAME}" /usr/local/bin/static-web-server && \
  chown -R "${SC_USER_NAME}:${SC_USER_NAME}" /public


USER ${SC_USER_NAME}

FROM server-base as production
# front-end client last we copy the client application directly inside
COPY --from=build-client \
  --chown=${SC_USER_NAME}:${SC_USER_NAME} \
  /project/build-output "/static-content"
ENV SC_BUILD_TARGET production

FROM server-base as development
ENV SC_BUILD_TARGET development
