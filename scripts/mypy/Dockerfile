# syntax=docker/dockerfile:1
ARG PYTHON_VERSION="3.10.10"
FROM python:${PYTHON_VERSION}-slim-buster as base


COPY requirements.txt /requirements.txt

RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install --upgrade pip \
  && pip install -r requirements.txt \
  && pip freeze

ENTRYPOINT ["mypy", "--config-file", "/config/mypy.ini", "--warn-unused-configs"]
