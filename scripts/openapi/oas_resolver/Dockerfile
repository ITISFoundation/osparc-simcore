# syntax=docker/dockerfile:1
# Usage:
# docker build . -t oas_resolver
# docker run -v /path/to/api:/input -v /path/to/compiled/file:/output oas_resolver /input/path/to/openapi.yaml /output/output_file.yaml
# NOTE: pinned exactly due to https://github.com/astral-sh/uv/issues/21692 (fixed in uv > 0.12.14)
ARG UV_VERSION="0.12.13"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build
# we docker image is built based on debian
FROM python:3.6-alpine

LABEL maintainer=sanderegg

VOLUME [ "/input" ]
VOLUME [ "/output" ]

WORKDIR /src

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/


RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install prance click openapi_spec_validator

ENTRYPOINT [ "prance", "compile" , "--backend=openapi-spec-validator"]
