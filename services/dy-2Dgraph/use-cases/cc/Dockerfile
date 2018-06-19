FROM simcore/services/jupyter-base-notebook:latest AS common

LABEL maintainer="sanderegg"

ARG NOTEBOOK_NAME=cc_oned.ipynb
ARG NOTEBOOK_FOLDER_NAME=cc-oned

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
    jupyter contrib nbextensions install --user && \
    jupyter dashboards quick-setup --sys-prefix && \    
    jupyter nbextension enable hide_input/main && \
    jupyter nbextension enable init_cell/main

# copy the notebook in
COPY --chown=jovyan:users ${NOTEBOOK_FOLDER_NAME}/${NOTEBOOK_NAME} .
RUN jupyter trust ${NOTEBOOK_NAME}

# download the simcore_sdk package
RUN mkdir packages && \
    cd packages && \
    git init && \
    git remote add origin -f https://github.com/sanderegg/osparc-simcore.git && \
    git config core.sparsecheckout true && \
    echo "packages/simcore-sdk/src/simcore_sdk/*" >> .git/info/sparse-checkout && \
    echo "packages/s3wrapper/src/s3wrapper/*" >> .git/info/sparse-checkout && \
    git pull --depth=1 origin analysis_2d_graph

# define where the inputs shall be defined
VOLUME /home/jovyan/data
VOLUME /home/jovyan/config

# starts notebook without token
ENV NOTEBOOK_URL=${NOTEBOOK_NAME}
ENV PYTHONPATH="./packages/packages/simcore-sdk/src:./packages/packages/s3wrapper/src"

COPY --chown=jovyan:users boot.sh boot.sh
RUN chmod +x boot.sh

FROM common AS development
ENV CREATE_DUMMY_TABLE=1
COPY --chown=jovyan:users develdbs3init.py .
CMD [ "/bin/sh", "boot.sh" ]

FROM common AS production
ENTRYPOINT [ "/bin/sh", "boot.sh" ]