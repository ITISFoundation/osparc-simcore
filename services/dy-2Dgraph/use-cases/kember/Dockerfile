FROM masu.speag.com/simcore/services/jupyter-base-notebook:1.3 AS common

LABEL maintainer="sanderegg"

ENV SIMCORE_NODE_UUID="-1" \
    S3_ENDPOINT="=1" \
    S3_ACCESS_KEY="-1" \
    S3_SECRET_KEY="-1" \
    S3_BUCKET_NAME="-1" \
    POSTGRES_ENDPOINT="-1" \
    POSTGRES_USER="-1" \
    POSTGRES_PASSWORD="-1" \
    POSTGRES_DB="-1"

EXPOSE 8888

# install git, ffmpeg
USER root
RUN apt-get update && \
    apt-get install -y \
    git
USER $NB_USER

# install requirements, install jupyter notebook extensions and enable necessary ones
COPY --chown=jovyan:users requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install jupyterthemes && \
    jt -t oceans16 && \
    jupyter contrib nbextensions install --user && \
    jupyter dashboards quick-setup --sys-prefix && \    
    jupyter nbextension enable hide_input/main && \
    jupyter nbextension enable init_cell/main

ENV PYTHONPATH="./packages/packages/simcore-sdk/src:./packages/packages/s3wrapper/src"

COPY --chown=jovyan:users boot.sh boot.sh
RUN chmod +x boot.sh

# -----------------------------------------------------------------------------
FROM common AS specialised
# set of arguments to copy the right notebook
ARG NOTEBOOK_NAME

# env to automatically open the notebook
ENV NOTEBOOK_URL=${NOTEBOOK_NAME}
# -----------------------------------------------------------------------------
FROM specialised AS development
# one can mount the packages
VOLUME /home/jovyan/packages/packages/simcore-sdk/src \
    /home/jovyan/packages/packages/s3wrapper/src
ARG JSON_CONFIGURATION
ENV USE_CASE_CONFIG_FILE=${JSON_CONFIGURATION}
# copy special configuration for development
COPY --chown=jovyan:users ${JSON_CONFIGURATION} .
# create dummy tables and dummy S3 data
ENV CREATE_DUMMY_TABLE=1
COPY --chown=jovyan:users develdbs3init.py .
CMD [ "/bin/sh", "boot.sh" ]
# -----------------------------------------------------------------------------
FROM specialised AS production
# set of arguments to copy the right notebook
ARG NOTEBOOK_NAME
# copy the notebook in the image
COPY --chown=jovyan:users ${NOTEBOOK_NAME} .
# download the simcore_sdk package
RUN mkdir packages && \
    cd packages && \
    git init && \
    git remote add origin -f https://github.com/ITISFoundation/osparc-simcore.git && \
    git config core.sparsecheckout true && \
    echo "packages/simcore-sdk/src/simcore_sdk/*" >> .git/info/sparse-checkout && \
    echo "packages/s3wrapper/src/s3wrapper/*" >> .git/info/sparse-checkout && \
    git pull --depth=1 origin master

ENTRYPOINT [ "/bin/sh", "boot.sh" ]