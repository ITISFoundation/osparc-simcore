# syntax=docker/dockerfile:1
# NOTE: This is a first step towards a devcontainer
#       to perform operations like pip-compile or auto-formatting
#       that preserves identical environment across developer machines
#
# Python version can be upgraded if:
#   - Has been patched several times (avoid using the very first release for production)
#   - Can be installed with pyenv (SEE pyenv install --list )
#
#
ARG PYTHON_VERSION="3.11.9"
ARG UV_VERSION="0.7"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build
# we docker image is built based on debian
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ENV VIRTUAL_ENV=/home/scu/.venv

RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
  set -eux && \
  apt-get update \
  && apt-get -y install --no-install-recommends\
  make \
  git \
  gawk \
  && apt-get clean -y


# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/

RUN uv venv "${VIRTUAL_ENV}"





# devenv
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install \
  pipreqs \
  pipdeptree && \
  uv pip list -vv
