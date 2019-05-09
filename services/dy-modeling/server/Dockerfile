FROM node:8.9.2 AS common

ENV NPM_CONFIG_LOGLEVEL warn

# Web server variables
ARG web_app_port=8080
ENV SIMCORE_WEB_HOSTNAME "0.0.0.0"
ENV SIMCORE_WEB_PORT $web_app_port
ENV SIMCORE_WEB_OUTDIR /home/node/source-output
EXPOSE $web_app_port

# S4L host and ports
ARG s4l_ip="0.0.0.0"
ARG s4l_port_app="9095"
ARG s4l_port_mod="9096"
ENV CS_S4L_HOSTNAME $s4l_ip
ENV CS_S4L_PORT_APP $s4l_port_app
ENV CS_S4L_PORT_MOD $s4l_port_mod
# ----------------------------------------------------------------
# COPY scripts/docker/healthcheck_curl_host.py /healthcheck/healthcheck_curl_host.py
# will start to run after interval every interval. fails after timeout. fail do not count if during start-period. will do # retries
# HEALTHCHECK --interval=10s --timeout=30s --start-period=1s --retries=3 CMD [ "python", "/healthcheck/healthcheck_curl_host.py", "http://localhost:9090" ]
# + /home/node/          json files
#    + source-output/    client source files
#    + source/  server   source files
WORKDIR /home/node/
COPY services/dy-modeling/server/package.json /home/node/package.json
VOLUME /home/node/source-output

# install python 3.6 for root
ENV PYENV_ROOT=/pyenv
RUN curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash && \
    export PATH="${PYENV_ROOT}/bin:$PATH" && \
    eval "$(pyenv init -)" && \
    eval "$(pyenv virtualenv-init -)" && \
    pyenv install 3.6.7 && \
    pyenv global 3.6.7 && \
    pip install --upgrade pip wheel setuptools

# ----------------------------------------------------------------
# set up oSparc env variables
ENV SIMCORE_NODE_UUID="-1" \
    SIMCORE_USER_ID="-1" \
    SIMCORE_NODE_BASEPATH="" \
    STORAGE_ENDPOINT="=1" \
    S3_ENDPOINT="=1" \
    S3_ACCESS_KEY="-1" \
    S3_SECRET_KEY="-1" \
    S3_BUCKET_NAME="-1" \
    POSTGRES_ENDPOINT="-1" \
    POSTGRES_USER="-1" \
    POSTGRES_PASSWORD="-1" \
    POSTGRES_DB="-1"

#--------------------Development------------------
FROM common AS development

VOLUME /home/node/devel
VOLUME /home/node/docker
VOLUME /home/node/packages
VOLUME /home/node/services
VOLUME /home/node/test-data
VOLUME /home/node/scripts/dy_services_helpers

ENV CREATE_DUMMY_TABLE 1
ENV USE_CASE_CONFIG_FILE="/home/node/devel/port_config.json"
ENV TEST_DATA_PATH="/home/node/test-data"
RUN npm install -y \
  && npm install nodemon -g

CMD ["/bin/bash", "/home/node/docker/boot.sh"]

#---------------------Production------------------
FROM common AS production
WORKDIR /home/node/

# install simcore packages
COPY packages/simcore-sdk /home/node/packages/simcore-sdk
COPY packages/s3wrapper /home/node/packages/s3wrapper
COPY services/storage/client-sdk /home/node/services/storage/client-sdk
# install packages but beware we need to use python 3.6 through pyenv
RUN export PATH="${PYENV_ROOT}/bin:$PATH" && \
    eval "$(pyenv init -)" && \
    pip install /home/node/packages/simcore-sdk &&\
    pip install /home/node/packages/s3wrapper && \
    pip install /home/node/services/storage/client-sdk/python

COPY --from=dy-modeling_client:latest /home/scu/client/build-output source-output
COPY services/dy-modeling/server/source /home/node/source
COPY services/dy-modeling/server/docker /home/node/docker
RUN npm install -y

ENTRYPOINT [ "/bin/bash", "/home/node/docker/boot.sh" ]
