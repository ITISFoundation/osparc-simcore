FROM python:3.6-alpine

ARG GIT_BRANCH
ARG GIT_REPOSITORY

RUN apk add --no-cache --virtual .build-deps \
    gcc \
    git \
    python3-dev \
    musl-dev \
    postgresql-dev \
    && git clone --single-branch --branch ${GIT_BRANCH} ${GIT_REPOSITORY} \
    && pip install osparc-simcore/packages/postgres-database[migration] \
    && apk del --no-cache .build-deps

# runtime dependency
RUN apk add --no-cache \
    bash \
    postgresql

COPY entrypoint.sh /home/entrypoint.sh


ENV POSTGRES_USER=scu \
    POSTGRES_PASSWORD=adminadmin \
    POSTGRES_HOST=postgres \
    POSTGRES_PORT=5432 \
    POSTGRES_DB=simcoredb

ENTRYPOINT [ "/bin/sh", "/home/entrypoint.sh" ]
CMD [ "sc-pg", "upgrade" ]
