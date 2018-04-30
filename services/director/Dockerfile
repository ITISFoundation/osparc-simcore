FROM python:3.6-alpine as common

LABEL maintainer="Sylvain Anderegg"

RUN adduser -D app

WORKDIR /home/app

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn==19.8.0

# TODO: does these environment variables are necessary here?
ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''
ENV LOCAL_MODE='True'

ENV FLASK_APP=director.py

VOLUME /var/run/docker.sock
EXPOSE 8001

# Development stage ---------------
FROM common as development

ENV FLASK_DEBUG=1

COPY boot.sh boot.sh
RUN chmod +x boot.sh

USER app
VOLUME /home/app

ENTRYPOINT ["./boot.sh"]

# Production stage -------------------
FROM common as production

COPY --chown=app:app . /home/app
RUN chmod +x boot.sh
#RUN chown -R app:app ./

USER app

ENTRYPOINT ["./boot.sh"]
