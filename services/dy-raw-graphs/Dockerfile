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

ENTRYPOINT ["/bin/sh", "docker/boot.sh"]

#-----------------Development-----------------------
FROM base as development

VOLUME $HOME/raw
VOLUME $HOME/docker
VOLUME $HOME/inputs

#-----------------Production----------------------
FROM base AS production

RUN git clone https://github.com/ITISFoundation/raw.git
WORKDIR $HOME/raw

RUN npm install -g bower
RUN bower install --allow-root

RUN cp js/analytics.sample.js js/analytics.js

COPY --chown=scu:scu docker docker
