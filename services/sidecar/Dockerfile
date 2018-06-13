FROM python:3.6-alpine as common

LABEL maintainer="Manuel Guidon <guidon@itis.ethz.ch"

RUN apk add --no-cache postgresql-dev gcc libc-dev

RUN pip install networkx sqlalchemy psycopg2 celery sqlalchemy-json docker pika minio ptvsd==3.0.0 \
    && pip list --format=columns

EXPOSE 8000

WORKDIR /work/sidecar

# NO clue why this does not work without explicitly specifying

FROM common as development

ENV PYTHONPATH="/work/packages/simcore-sdk/src:/work/packages/s3wrapper/src"
ENTRYPOINT celery -A sidecar worker -c 2 --loglevel=info

FROM common as production

ENV PYTHONPATH="/work/packages/simcore-sdk/src:/work/packages/s3wrapper/src"
ENTRYPOINT celery -A sidecar worker -c 2 --loglevel=info
