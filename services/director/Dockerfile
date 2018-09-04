FROM python:3.6-alpine as common

LABEL maintainer="sanderegg"

RUN apk add --no-cache gcc libc-dev
# create standard user scu
RUN adduser -D -u 8004 scu
USER scu

# RUN addgroup docker && addgroup user \
#   && adduser -D app \
  # && addgroup app app && addgroup app docker

ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''

EXPOSE 8001

WORKDIR /home/scu

# + /home/scu/            $HOME, $WORKDIR,
#    + src/            $PYTHONPATH
#    + boot.sh



# create virtual environment
RUN python -m venv venv \
    && chown -R scu:scu venv \
    && /home/scu/venv/bin/pip install --upgrade pip wheel setuptools

# copy boot
COPY --chown=scu:scu boot.sh boot.sh
RUN chmod +x boot.sh

# VOLUME /var/run/docker.sock # FIXME: fails when docker-compose run in production !?

# --------------------------Development stage -------------------
FROM common as development

ENV DEBUG 1
# mount the director folder here
VOLUME /home/scu/src

USER root

CMD ["/bin/sh", "./boot.sh"]

# --------------------------Production stage -------------------
FROM common as production

ENV DEBUG 0
COPY --chown=scu:scu . /home/scu/src
RUN /home/scu/venv/bin/pip install /home/scu/src \
    && rm -rf /home/scu/src

# FIXME: this is the only way to get access to docker sockets !?
USER root

ENTRYPOINT ["/bin/sh", "./boot.sh"]
