FROM joseluisq/static-web-server:1.15.0-alpine as base

LABEL maintainer=neagu@itis.swiss

# front-end client last (image name is the path to the Dockerfile)
COPY --from=client/tools/qooxdoo-kit/builder:latest --chown=scu:scu \
    /project/build-output "/static-content"

FROM base as build

FROM base as development

FROM base as production