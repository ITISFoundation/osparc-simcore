
ARG LOCUST_VERSION
FROM locustio/locust:${LOCUST_VERSION:-2.29.1}


RUN pip3 --version && \
  pip3 install \
  faker \
  locust-plugins \
  locust-plugins[dashboards] \
  pydantic \
  pydantic-settings \
  tenacity &&\
  pip3 freeze --verbose
