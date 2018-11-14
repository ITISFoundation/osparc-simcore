FROM continuumio/miniconda
MAINTAINER Manuel Guidon <guidon@itis.ethz.ch>

RUN conda install flask

EXPOSE 5001

WORKDIR /work
CMD ["python", "app.py"]
