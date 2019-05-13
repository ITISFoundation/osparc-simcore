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
    python3-pip && \
    python3 -V

# install python 3.6 for root and also for www-data
ENV PYENV_ROOT=/pyenv
RUN curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash && \
    export PATH="${PYENV_ROOT}/bin:$PATH" && \
    eval "$(pyenv init -)" && \
    eval "$(pyenv virtualenv-init -)" && \
    apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
    xz-utils tk-dev libffi-dev liblzma-dev && \
    pyenv install 3.6.7 && \
    pyenv global 3.6.7 && \
    pip install --upgrade pip wheel setuptools

# get the patched visualizer
COPY --from=visualizer /home/node/visualizer/dist /opt/paraview/install/share/paraview-5.5/web/visualizer/www
WORKDIR /home/root
# ----------------------------------------------------------------
COPY scripts/docker/healthcheck_curl_host.py /healthcheck/healthcheck_curl_host.py
# will start to run after interval every interval. fails after timeout. fail do not count if during start-period. will do # retries
#HEALTHCHECK --interval=10s --timeout=30s --start-period=1s --retries=3 CMD [ "python3", "/healthcheck/healthcheck_curl_host.py", "http://localhost:80/visualizer" ]

# set up oSparc env variables
ENV SIMCORE_NODE_UUID="-1" \
    SIMCORE_USER_ID="-1" \
    STORAGE_ENDPOINT="=1" \
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
RUN pip3 install --upgrade pip wheel setuptools

# copy scripts
COPY services/dy-3dvis/simcoreparaviewweb/docker /home/root/docker
COPY services/dy-3dvis/simcoreparaviewweb/config /home/root/config

# RUN chmod +x docker/boot.sh
# apply apache config changer script
# RUN chmod +x docker/apachePatch.sh
RUN mkdir /home/root/trigger && \
    chmod 777 /home/root/trigger
# apply paraview launcher modifier script
# RUN chmod +x docker/visualizer_launcher_patch.sh
#------------------------------------------
FROM common as development
VOLUME /home/root/cgi_scripts
VOLUME /home/root/devel
VOLUME /home/root/packages
VOLUME /home/root/services
VOLUME /home/root/test-data
VOLUME /home/root/scripts/dy_services_helpers
ENV CREATE_DUMMY_TABLE 1
ENV USE_CASE_CONFIG_FILE="devel/port_config.json"
ENV TEST_DATA_PATH="/test-data"
# Need to use entrypoint as base image's entrypoint must be overriden
ENTRYPOINT [ "/bin/bash", "docker/boot.sh" ]
#------------------------------------------
FROM common AS production
# install simcore packages
COPY packages/simcore-sdk /home/root/packages/simcore-sdk
COPY packages/s3wrapper /home/root/packages/s3wrapper
COPY services/storage/client-sdk /home/root/services/storage/client-sdk
# install packages but beware we need to use python 3.6 through pyenv
RUN export PATH="${PYENV_ROOT}/bin:$PATH" && \
    eval "$(pyenv init -)" && \
    pip install /home/root/packages/simcore-sdk &&\
    pip install /home/root/packages/s3wrapper && \
    pip install /home/root/services/storage/client-sdk/python
# copy script to get the inputs inside the local file system
COPY services/dy-3dvis/simcoreparaviewweb/cgi_scripts /home/root/cgi_scripts
ENTRYPOINT [ "/bin/bash", "docker/boot.sh" ]
