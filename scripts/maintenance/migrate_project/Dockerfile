# syntax=docker/dockerfile:1
FROM python:3.11.9-buster

RUN curl https://rclone.org/install.sh | bash && \
  rclone --version

WORKDIR /scripts

COPY packages/postgres-database postgres-database
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  cd postgres-database && pip install .

COPY packages/settings-library settings-library
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  cd settings-library && pip install .

COPY scripts/maintenance/migrate_project/requirements.txt /scripts/requirements.txt
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip \
  pip install -r /scripts/requirements.txt

COPY scripts/maintenance/migrate_project/src/*.py /scripts/
