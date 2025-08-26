# syntax=docker/dockerfile:1
ARG UV_VERSION="0.7"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build
# we docker image is built based on debian
FROM python:3.11.9-buster

RUN curl https://rclone.org/install.sh | bash && \
  rclone --version

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/

WORKDIR /scripts

COPY packages/postgres-database postgres-database
RUN --mount=type=cache,target=/root/.cache/uv \
  cd postgres-database && uv pip install .

COPY packages/settings-library settings-library
RUN --mount=type=cache,target=/root/.cache/uv \
  cd settings-library && uv pip install .

COPY scripts/maintenance/migrate_project/requirements.txt /scripts/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install -r /scripts/requirements.txt

COPY scripts/maintenance/migrate_project/src/*.py /scripts/
