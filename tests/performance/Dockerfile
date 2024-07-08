
ARG LOCUST_VERSION
FROM locustio/locust:${LOCUST_VERSION}


RUN pip3 --version && \
  pip3 install \
  faker \
  locust-plugins==2.1.1 \
  pydantic \
  pydantic-settings \
  tenacity &&\
  pip3 freeze --verbose
