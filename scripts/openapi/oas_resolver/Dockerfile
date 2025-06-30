# syntax=docker/dockerfile:1
# Usage:
# docker build . -t oas_resolver
# docker run -v /path/to/api:/input -v /path/to/compiled/file:/output oas_resolver /input/path/to/openapi.yaml /output/output_file.yaml
ARG UV_VERSION="0.7"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build
# we docker image is built based on debian
FROM python:3.6-alpine

LABEL maintainer=sanderegg

VOLUME [ "/input" ]
VOLUME [ "/output" ]

WORKDIR /src

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/

# update pip
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install --upgrade \
  wheel \
  setuptools

RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install prance click openapi_spec_validator

ENTRYPOINT [ "prance", "compile" , "--backend=openapi-spec-validator"]
