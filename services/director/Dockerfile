FROM continuumio/miniconda3
# TODO: see if can reduce to python:3.6-alpine

LABEL maintainer="Sylvain Anderegg"

# TODO: user requirements.txt instead
RUN conda update conda
RUN conda install flask
RUN pip install docker

ENV FLASK_APP=director.py
# TODO: does these environment variables are necessary here?
ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''
ENV LOCAL_MODE='True'

# TODO: in dev mode this is mounted
COPY . /home/app

WORKDIR /home/app
VOLUME /var/run/docker.sock
EXPOSE 8001

# TODO: warning this is a development server! uuse unicorn instead!
ENTRYPOINT [ "flask", "run", "--host=0.0.0.0", "--port=8001"]
