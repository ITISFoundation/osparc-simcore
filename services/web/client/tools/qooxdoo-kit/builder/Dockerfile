#
# Compiles client's source code within an image based in qooxdoo-kit
#
# Note: context at osparc-simcore/services/web/client expected
#
ARG tag
FROM itisfoundation/qooxdoo-kit:${tag} as touch

WORKDIR /project
ENV PATH=/home/node/node_modules/.bin:${PATH}

RUN mkdir /project/build-output

FROM touch as build-client

# Installs contributions
COPY --chown=node:node compile.json compile.json
COPY --chown=node:node qx-lock.json qx-lock.json
COPY --chown=node:node Manifest.json Manifest.json

# Install packages (warning: cache might keep these library out-of-date!)
# TODO: should we freeze packages??
RUN qx package update &&\
  qx package install &&\
  ls -la qx_packages
# -> /project/qx_packages


# Copy sources and compile inside the image
COPY --chown=node:node source source
COPY --chown=node:node Manifest.json Manifest.json

ARG VCS_URL=undefined
ARG VCS_REF="undefined"
ARG VCS_REF_CLIENT=undefined
ARG VCS_STATUS_CLIENT=undefined

# Increase to 5 GB, this does not fix the probable memory leak but allows to go further
ENV NODE_OPTIONS="--max-old-space-size=5120"

# this nice call prints the actual heap size limit in GB
RUN node -e 'console.log(v8.getHeapStatistics().heap_size_limit/(1024*1024))' && \
  qx compile --target=build \
  --set-env osparc.vcsOriginUrl="${VCS_URL}" \
  --set-env osparc.vcsRef="${VCS_REF}" \
  --set-env osparc.vcsRefClient="${VCS_REF_CLIENT}" \
  --set-env osparc.vcsStatusClient="${VCS_STATUS_CLIENT}" && \
  ls -la build-output
# -> /project/build-output
