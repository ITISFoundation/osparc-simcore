ARG PYTHON_VERSION="3.10.10"
FROM python:${PYTHON_VERSION}-slim-buster as base


COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip \
  && pip install -r requirements.txt

ENTRYPOINT ["mypy", "--config-file", "/config/mypy.ini", "--warn-unused-configs"]
