FROM continuumio/miniconda3
LABEL maintainer="Sylvain Anderegg"

RUN conda update conda
RUN conda install flask
RUN pip install docker

WORKDIR /home/app

ENV FLASK_APP=director.py
ENV REGISTRY_AUTH = ''
ENV REGISTRY_USER = ''
ENV REGISTRY_PW = ''
ENV REGISTRY_URL = ''
ENV LOCAL_MODE='True'
EXPOSE 8001
COPY /director /home/app

ENTRYPOINT [ "python", "director.py" ]