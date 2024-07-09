
ARG LOCUST_VERSION
FROM locustio/locust:${LOCUST_VERSION}


RUN pip3 --version && \
  pip3 install \
  faker \
  locust-plugins \
  pydantic \
  pydantic-settings \
  tenacity &&\
  pip3 freeze --verbose
