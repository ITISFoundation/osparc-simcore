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

RUN npm install express

# ----------------------------------------------------------------
# set up oSparc env variables
ENV RAWGRAPHS_BASEPATH="/raw" \
    RAWGRAPHS_INPUTS="/inputs"

#-----------------Development-----------------------
FROM base as development

VOLUME $HOME/raw
VOLUME $HOME/docker
VOLUME $HOME/inputs
VOLUME $HOME/server

WORKDIR $HOME/raw
ENTRYPOINT ["/bin/sh", "../docker/boot.sh"]

#-----------------Production----------------------
FROM base AS production

RUN git clone https://github.com/ITISFoundation/raw.git
WORKDIR $HOME/raw
RUN npm install -g bower
RUN bower install --allow-root

WORKDIR $HOME
COPY --chown=scu:scu docker docker
COPY --chown=scu:scu server server

WORKDIR $HOME/raw
CMD ["/bin/sh", "../docker/boot.sh"]