FROM joseluisq/static-web-server:1.15.0-alpine as base

LABEL maintainer=neagu@itis.swiss

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
    SC_USER_NAME=scu \
    SC_BUILD_TARGET=base \
    SC_BOOT_MODE=default

RUN adduser \
    --uid ${SC_USER_ID} \
    --disabled-password \
    --gecos "" \
    --shell /bin/sh \
    --home /home/${SC_USER_NAME} \
    ${SC_USER_NAME}

# front-end client last (image name is the path to the Dockerfile)
COPY --from=client/tools/qooxdoo-kit/builder:latest --chown=scu:scu \
    /project/build-output "/static-content"

FROM base as build
ENV SC_BUILD_TARGET build

FROM base as production
ENV SC_BUILD_TARGET production

FROM base as development
ENV SC_BUILD_TARGET development
