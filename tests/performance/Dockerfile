
ARG LOCUST_VERSION
FROM locustio/locust:${LOCUST_VERSION}


RUN pip3 --version && \
  pip3 install \
  faker \
  python-dotenv \
  locust-plugins==1.2.0 &&\
  pip3 freeze --verbose
