ARG PYTHON_VERSION="3.9.12"
FROM python:${PYTHON_VERSION}-slim-buster as base


COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip \
  && pip install -r requirements.txt

ENTRYPOINT ["mypy", "--config-file", "/config/mypy.ini", "--warn-unused-configs"]
