FROM python:3.6-alpine

RUN apk add --no-cache --virtual .build-deps \
    gcc \
    python3-dev \
    musl-dev \
    postgresql-dev \
    && git clone https://github.com/ITISFoundation/osparc-simcore.git \
    && pip install osparc-simcore\packages\postgres-database[migration] \
    && apk del --no-cache .build-deps

ENTRYPOINT ["sc-pg", "discover", "--user ${POSTGRES_USER}", "--password ${POSTGRES_PASSWORD}", "--host ${POSTGRES_HOST"]
ENTRYPOINT ["sc-pg", "upgrade"]
