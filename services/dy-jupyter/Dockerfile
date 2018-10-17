ARG BASE_IMAGE=jupyter/base-notebook
FROM ${BASE_IMAGE}  AS base

LABEL maintainer="sanderegg"
EXPOSE 8888
# ----------------------------------------------------------------
# Add a python2 kernel in the notebook
# Create a Python 2.x environment using conda including at least the ipython kernel
# and the kernda utility. Add any additional packages you want available for use
# in a Python 2 notebook to the first line here (e.g., pandas, matplotlib, etc.)
RUN conda create --quiet --yes -p $CONDA_DIR/envs/python2 python=2.7 ipython ipykernel kernda && \
    conda clean -tipsy
USER root
# Create a global kernelspec in the image and modify it so that it properly activates
# the python2 conda environment.
RUN $CONDA_DIR/envs/python2/bin/python -m ipykernel install && \
$CONDA_DIR/envs/python2/bin/kernda -o -y /usr/local/share/jupyter/kernels/python2/kernel.json
USER $NB_USER
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
# ----------------------------------------------------------------
# set up oSparc labels
ARG SERVICE_KEY
ARG SERVICE_VERSION
ARG SERVICE_NAME
ARG BUILD_DATE
ARG VCS_REF

LABEL io.simcore.key='{"key": "${SERVICE_KEY}"}' \
        io.simcore.tag='{"tag": "${SERVICE_VERSION}"}' \
        io.simcore.name='{"name": "${SERVICE_NAME}"}' \
        io.simcore.description='{"description": "Jupyter notebook"}' \
        io.simcore.contact='{"contact": "anderegg@itis.swiss"}' \
        io.simcore.authors='{"authors": [{"name": "sanderegg", "email": ""anderegg@itis.swiss"", "affiliation": "ITIS Foundation"}]}' \
        io.simcore.inputs='{"inputs": [{"key": "input_1", "label": "input 1", "desc": "file input", "type": "file-url", "value": "null"}]}' \
        io.simcore.outputs='{"outputs": [{"key": "output_1", "label": "output 1", "desc": "file output", "type": "file-url", "value": "null"}]}' \
        io.simcore.viewer='{"viewer":{"ip":null, "port":null}}' \
        simcore.service.settings='[{"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}]' \
        org.label-schema.schema-version="1.0" \
        org.label-schema.build-date="${BUILD_DATE}" \
        org.label-schema.vcs-ref="${VCS_REF}"
# ----------------------------------------------------------------
# install simcore-sdk
COPY --chown=jovyan:users packages/simcore-sdk /packages/simcore-sdk
COPY --chown=jovyan:users packages/s3wrapper /packages/s3wrapper
RUN pip install --upgrade pip && \
    pip install /packages/simcore-sdk &&\
    pip install /packages/s3wrapper
# ----------------------------------------------------------------
# configure notebook
RUN pip install jupyter_contrib_nbextensions && \
    jupyter contrib nbextensions install --user && \
    jupyter nbextension enable hide_input/main && \
    jupyter nbextension enable init_cell/main
# ----------------------------------------------------------------
# prepare for booting
COPY --chown=jovyan:users services/dy-jupyter/docker /docker

# ----------------------------------------------------------------
# put demo file
COPY --chown=jovyan:users services/dy-jupyter/demo /home/jovyan/demo

FROM base AS development
ENV CREATE_DUMMY_TABLE=1
ENV USE_CASE_CONFIG_FILE="devel/port_config.json"
COPY --chown=jovyan:users services/dy-jupyter/devel /home/jovyan/devel
RUN pip install -r /home/jovyan/devel/requirements.txt
CMD [ "/bin/sh", "/docker/boot.sh" ]

FROM base AS production
ENTRYPOINT [ "/bin/sh", "/docker/boot.sh" ]