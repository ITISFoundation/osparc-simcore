ARG DOCKER_BUILD_REGISTRY_PORT=5000
FROM localhost:${DOCKER_BUILD_REGISTRY_PORT}/client/tools/qooxdoo-kit/builder:latest as app_source

FROM joseluisq/static-web-server:1.16.0-alpine as base

LABEL maintainer=neagu@itis.swiss

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN adduser -D -u ${SC_USER_ID} -s /bin/sh -h /home/${SC_USER_NAME} ${SC_USER_NAME}

# front-end client last (image name is the path to the Dockerfile)

COPY --from=app_source --chown=${SC_USER_NAME}:${SC_USER_NAME} \
  /project/build-output "/static-content"

# changing ownership of static-web-server files
RUN chown -R ${SC_USER_NAME}:${SC_USER_NAME} /entrypoint.sh
RUN chown -R ${SC_USER_NAME}:${SC_USER_NAME} /usr/local/bin/static-web-server
RUN chown -R ${SC_USER_NAME}:${SC_USER_NAME} /public

USER ${SC_USER_NAME}

FROM base as build
ENV SC_BUILD_TARGET build

FROM base as production
ENV SC_BUILD_TARGET production

FROM base as development
ENV SC_BUILD_TARGET development
