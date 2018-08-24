FROM python:3.6-alpine as common

LABEL maintainer="Manuel Guidon <guidon@itis.ethz.ch"

RUN apk add --no-cache \
      postgresql-dev \
      gcc \
      libc-dev

RUN pip install --upgrade \
      pip \
      wheel \
      setuptools

WORKDIR /work
# Buil context set at repo's root
COPY services/sidecar/requirements requirements

RUN pip install -r requirements/base.txt &&\
    rm -rf requirements

# Keeps same folder structure as in repo so we can reuse relative paths
RUN mkdir -p /work/packages &&\
    mkdir -p /work/services/sidecar

EXPOSE 8000


# --------------------------Development stage -------------------
FROM common as development

VOLUME /work/packages
VOLUME /work/services/sidecar

ENV DEBUG 1
WORKDIR /work/services/sidecar
CMD ./boot.sh
# FIXME: executing this as root will create folders (e.g. eggs) in the mapped


# --------------------------Production stage -------------------
FROM common as production

# Buil context set at repo's root
COPY packages /work/packages
COPY services/sidecar /work/services/sidecar

WORKDIR /work/services/sidecar

RUN pip install -r requirements/prod.txt ;\
    pip list &&\
    mv boot.sh /work &&\
    rm -rf /work/packages &&\
    rm -rf /work/services/sidecar

ENV DEBUG 0
WORKDIR /work
ENTRYPOINT ./boot.sh
