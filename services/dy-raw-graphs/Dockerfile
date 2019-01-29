FROM node:8.15.0-alpine as base

LABEL maintainer=odeimaiz

# non-root user 'scu'
RUN adduser -D -u 8004 scu

RUN apk add --no-cache \
    su-exec

ENV HOME /home/scu

EXPOSE 4000

WORKDIR $HOME

RUN apk update && \
    apk upgrade && \
    apk add python3 && \
    apk add git

RUN pip install --upgrade pip wheel setuptools

RUN npm install express

# ----------------------------------------------------------------
# set up oSparc env variables
ENV SIMCORE_NODE_UUID="-1" \
    SIMCORE_USER_ID="-1" \
    SIMCORE_NODE_BASEPATH="/raw" \
    STORAGE_ENDPOINT="=1" \
    RAWGRAPHS_INPUT_PATH="/inputs" \
    S3_ENDPOINT="=1" \
    S3_ACCESS_KEY="-1" \
    S3_SECRET_KEY="-1" \
    S3_BUCKET_NAME="-1" \
    POSTGRES_ENDPOINT="-1" \
    POSTGRES_USER="-1" \
    POSTGRES_PASSWORD="-1" \
    POSTGRES_DB="-1"

#-----------------Development-----------------------
FROM base as development

VOLUME $HOME/packages
VOLUME $HOME/services/storage/client-sdk

VOLUME $HOME/raw
VOLUME $HOME/docker
VOLUME $HOME/inputs
VOLUME $HOME/server

WORKDIR $HOME/raw
ENTRYPOINT ["/bin/sh", "../docker/boot.sh"]

#-----------------Production----------------------
FROM base AS production

# install simcore packages
COPY packages/simcore-sdk $HOME/packages/simcore-sdk
COPY packages/s3wrapper $HOME/packages/s3wrapper
COPY services/storage/client-sdk $HOME/services/storage/client-sdk
# install packages but beware we need to use python 3.6 through pyenv
RUN pip install $HOME/packages/simcore-sdk &&\
    pip install $HOME/packages/s3wrapper && \
    pip install $HOME/services/storage/client-sdk/python

RUN git clone https://github.com/ITISFoundation/raw.git
WORKDIR $HOME/raw
RUN npm install -g bower
RUN bower install --allow-root

WORKDIR $HOME
COPY --chown=scu:scu docker docker
COPY --chown=scu:scu server server

WORKDIR $HOME/raw
CMD ["/bin/sh", "../docker/boot.sh"]