FROM python:3.6-alpine

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

# TODO: in dev mode this is instead mounted from host
COPY . /home/app
RUN chmod +x boot.sh
RUN chown -R app:app ./

USER app

VOLUME /var/run/docker.sock
EXPOSE 8001

ENTRYPOINT ["./boot.sh"]

# TODO: warning this is a development server! use unicorn instead!
# CMD [ "flask", "run", "--host=0.0.0.0", "--port=8001"]
