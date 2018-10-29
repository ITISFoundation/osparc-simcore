# apply patch to visualizer
FROM node:8.12.0 AS visualizer
WORKDIR /home/node
RUN git clone --branch v3.1.6 https://github.com/Kitware/visualizer.git
WORKDIR /home/node/visualizer
COPY services/dy-3dvis/simcoreparaviewweb/rebrand-osparc/to-be-copied .
COPY services/dy-3dvis/simcoreparaviewweb/rebrand-osparc/rebrand-osparc.patch rebrand-osparc.patch
RUN git apply rebrand-osparc.patch && \
    npm install && \
    npm run build:release && \
    npm link && \
    cp src/*.png dist
# ----------------------------------------------------------------
# build visualizer service
FROM kitware/paraviewweb:pvw-visualizer-osmesa-master  AS common

LABEL maintainer="sanderegg"
ENV PARAVIEW_INPUT_PATH="/data"

# install git, pip
RUN apt-get update && \
    apt-get install -y \
    python3-pip
# get the patched visualizer
COPY --from=visualizer /home/node/visualizer/dist /opt/paraview/install/share/paraview-5.5/web/visualizer/www
WORKDIR /home/root
# ----------------------------------------------------------------
# set up oSparc env variables
ENV SIMCORE_NODE_UUID="-1" \
    S3_ENDPOINT="=1" \
    S3_ACCESS_KEY="-1" \
    S3_SECRET_KEY="-1" \
    S3_BUCKET_NAME="-1" \
    POSTGRES_ENDPOINT="-1" \
    POSTGRES_USER="-1" \
    POSTGRES_PASSWORD="-1" \
    POSTGRES_DB="-1"

# special paraview variables
ENV SERVER_PORT="-1"  \
    HOST_NAME="-1"
# update pip
RUN pip3 install --upgrade pip

# copy scripts
COPY services/dy-3dvis/simcoreparaviewweb/scripts /home/root/scripts
COPY services/dy-3dvis/simcoreparaviewweb/config /home/root/config

RUN chmod +x scripts/boot.sh
# apply apache config changer script
RUN chmod +x scripts/apachePatch.sh
RUN mkdir /home/root/trigger && \
    chmod 777 /home/root/trigger
# apply paraview launcher modifier script
RUN chmod +x scripts/visualizer_launcher_patch.sh
#------------------------------------------
FROM common as development
VOLUME /home/root/src
VOLUME /home/root/devel
VOLUME /home/root/packages
VOLUME /home/root/test-data
ENV CREATE_DUMMY_TABLE 1
ENV USE_CASE_CONFIG_FILE="devel/devel-dbconfiguration.json"
ENV TEST_DATA_PATH="/test-data"
# Need to use entrypoint as base image's entrypoint must be overriden
ENTRYPOINT [ "/bin/bash", "scripts/boot.sh" ]
#------------------------------------------
FROM common AS production
# install simcore packages
COPY packages/simcore-sdk /home/root/packages/simcore-sdk
COPY packages/s3wrapper /home/root/packages/s3wrapper
# copy the default notebook
RUN pip install /home/root/packages/simcore-sdk &&\
    pip install /home/root/packages/s3wrapper
# copy script to get the inputs inside the local file system
COPY services/dy-3dvis/simcoreparaviewweb/src /home/root/src
ENTRYPOINT [ "/bin/bash", "scripts/boot.sh" ]