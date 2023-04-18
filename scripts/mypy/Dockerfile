ARG PYTHON_VERSION="3.10.10"
FROM python:${PYTHON_VERSION}-slim-buster as base


COPY requirements.txt /requirements.txt

RUN pip --no-cache-dir install --upgrade pip \
  && pip --no-cache-dir install -r requirements.txt \
  && pip --no-cache-dir freeze

ENTRYPOINT ["mypy", "--config-file", "/config/mypy.ini", "--warn-unused-configs"]
