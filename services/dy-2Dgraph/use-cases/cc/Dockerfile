FROM simcore/services/jupyter-base-notebook:latest AS common

LABEL maintainer="sanderegg"

ENV SIMCORE_PIPELINE_ID="-1"
ENV SIMCORE_NODE_UUID="-1"
ENV S3_ENDPOINT="=1"
ENV S3_ACCESS_KEY="-1"
ENV S3_SECRET_KEY="-1"
ENV S3_BUCKET_NAME="-1"
ENV POSTGRES_ENDPOINT="-1"
ENV POSTGRES_USER="-1"
ENV POSTGRES_PASSWORD="-1"
ENV POSTGRES_DB="-1"

EXPOSE 8888

# call date -u +”%Y-%m-%dT%H:%M:%SZ” in a bash
ARG VCS_REF
ARG BUILD_DATE
# call git rev-parse — short HEAD in a bash
ARG BUILD_VERSION

# Labels.
LABEL org.label-schema.schema-version="1.0"
LABEL org.label-schema.build-date=$BUILD_DATE
LABEL org.label-schema.name="simcore/services/cc-1d-graphs"
LABEL org.label-schema.description="Colleen Clancy 1D graph analysis"
LABEL org.label-schema.url="https://www.itis.ethz.ch"
LABEL org.label-schema.vcs-url="https://github.com/ITISFoundation/osparc-simcore"
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.vendor="IT'IS foundation"
LABEL org.label-schema.version=$BUILD_VERSION
LABEL org.label-schema.docker.cmd="docker run -it --rm -p 8888:8888 cc-1d-graphs"
# service runtime settings
LABEL simcore.service.settings='[{"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}]'

# install git, ffmpeg
USER root
RUN apt-get update && \
    apt-get install -y \
    git \
    ffmpeg
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

# download the simcore_sdk package
RUN mkdir packages && \
    cd packages && \
    git init && \
    git remote add origin -f https://github.com/sanderegg/osparc-simcore.git && \
    git config core.sparsecheckout true && \
    echo "packages/simcore-sdk/src/simcore_sdk/*" >> .git/info/sparse-checkout && \
    echo "packages/s3wrapper/src/s3wrapper/*" >> .git/info/sparse-checkout && \
    git pull --depth=1 origin analysis_2d_graph

ENV PYTHONPATH="./packages/packages/simcore-sdk/src:./packages/packages/s3wrapper/src"

# define where the inputs shall be defined
VOLUME /home/jovyan/data
VOLUME /home/jovyan/config

COPY --chown=jovyan:users boot.sh boot.sh
RUN chmod +x boot.sh
# -----------------------------------------------------------------------------
FROM common AS specialised
# set of arguments to copy the right notebook
ARG NOTEBOOK_NAME=cc_oned.ipynb
ARG NOTEBOOK_FOLDER_NAME=cc-oned
# copy the notebook in the image
COPY --chown=jovyan:users ${NOTEBOOK_FOLDER_NAME}/${NOTEBOOK_NAME} .
# set jupyter to trust the notebook
RUN jupyter trust ${NOTEBOOK_NAME}
# env to automatically open the notebook
ENV NOTEBOOK_URL=${NOTEBOOK_NAME}
# -----------------------------------------------------------------------------
FROM specialised AS development
ARG JSON_CONFIGURATION_FOLDER=cc-oned
ARG JSON_CONFIGURATION=cc_config-oned.json
ENV USE_CASE_CONFIG_FILE=${JSON_CONFIGURATION}
# copy special configuration for development
COPY --chown=jovyan:users ${JSON_CONFIGURATION_FOLDER}/${JSON_CONFIGURATION} .
# create dummy tables and dummy S3 data
ENV CREATE_DUMMY_TABLE=1
COPY --chown=jovyan:users develdbs3init.py .
CMD [ "/bin/sh", "boot.sh" ]
# -----------------------------------------------------------------------------
FROM specialised AS production
ENTRYPOINT [ "/bin/sh", "boot.sh" ]