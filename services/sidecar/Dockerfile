FROM python:3.6-alpine as common

LABEL maintainer="Manuel Guidon <guidon@itis.ethz.ch"

WORKDIR /work/sidecar

RUN apk add --no-cache postgresql-dev gcc libc-dev

COPY requirements.txt requirements.txt

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip list --format=columns

#RUN pip install networkx sqlalchemy psycopg2 celery sqlalchemy-json docker pika minio \
#    && pip list --format=columns

EXPOSE 8000


FROM common as development

VOLUME /work/sidecar
VOLUME /work/packages

# NO clue why this does not work without explicitly specifying
ENV PYTHONPATH="/work/packages/simcore-sdk/src:/work/packages/s3wrapper/src"
ENTRYPOINT celery -A sidecar worker -c 2 --loglevel=info

FROM common as production

# NO clue why this does not work without explicitly specifying
ENV PYTHONPATH="/work/packages/simcore-sdk/src:/work/packages/s3wrapper/src"
ENTRYPOINT celery -A sidecar worker -c 2 --loglevel=info
