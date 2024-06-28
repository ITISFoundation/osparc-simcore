# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.14"
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8

# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
  VIRTUAL_ENV=/home/scu/.venv

# Ensures that the python and pip executables used in the image will be
# those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"


# NOTE: install https://github.com/astral-sh/uv ultra-fast rust-based pip replacement
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install uv~=0.2

RUN \
  --mount=type=cache,mode=0755,target=/root/.cache/uv \
  --mount=type=bind,source=./requirements.txt,target=requirements.txt \
  uv venv "${VIRTUAL_ENV}" \
  && uv pip install --upgrade pip wheel setuptools \
  && uv pip install -r requirements.txt \
  && uv pip list

ENTRYPOINT ["mypy", "--config-file", "/config/mypy.ini", "--warn-unused-configs"]
