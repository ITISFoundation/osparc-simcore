FROM python:3.6-alpine as common

LABEL maintainer="sanderegg"

RUN addgroup docker && addgroup user \
  && adduser -D app \
  && addgroup app app && addgroup app docker

USER app

ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''
ENV PYTHONPATH=/home/app/source
ENV FLASK_APP=director.py
ENV FLASK_DEBUG=0

WORKDIR /home/app

# + /home/app/            $HOME, $WORKDIR,
#    + test/
#    + source/            $PYTHONPATH
#    + requirements.txt
#    + boot.sh

COPY --chown=app:app requirements.txt requirements.txt

RUN python -m venv venv \
 && chown -R app:app venv

RUN venv/bin/pip install --upgrade pip \
 && venv/bin/pip install -r requirements.txt

COPY --chown=app:app boot.sh boot.sh
RUN chmod +x boot.sh

# VOLUME /var/run/docker.sock # FIXME: fails when docker-compose run in production !?
EXPOSE 8001

# --------------------------Development stage -------------------
FROM common as development

ENV FLASK_DEBUG=1

VOLUME /home/app/source

USER root

CMD ["/bin/sh", "./boot.sh"]

# --------------------------Production stage -------------------
FROM common as production

RUN venv/bin/pip install gunicorn==19.8.0

# TODO: set non-root id
COPY --chown=1000:docker source source

# FIXME: this is the only way to get access to docker sockets !?
USER root

ENTRYPOINT ["/bin/sh", "./boot.sh"]
