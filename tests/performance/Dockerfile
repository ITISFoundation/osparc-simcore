
ARG LOCUST_VERSION
FROM locustio/locust:${LOCUST_VERSION}


RUN pip3 --version && \
  pip3 install \
  faker \
  python-dotenv \
  locust-plugins==2.1.1 &&\
  pip3 freeze --verbose
