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
# configure notebook
RUN pip install --upgrade pip && \
    pip install jupyter_contrib_nbextensions && \
    pip install jupyterthemes && \
    jt -t oceans16 && \
    jupyter contrib nbextensions install --user && \
    jupyter nbextension enable hide_input/main && \
    jupyter nbextension enable init_cell/main
# ----------------------------------------------------------------
# prepare for booting
COPY --chown=jovyan:users services/dy-jupyter/docker /docker

ENV NOTEBOOK_URL="work/notebook.ipynb"
# ----------------------------------------------------------------
FROM base AS development
VOLUME /packages
VOLUME /home/jovyan/devel
VOLUME /home/jovyan/work
ENV CREATE_DUMMY_TABLE=1
ENV USE_CASE_CONFIG_FILE="devel/port_config.json"
ENV INIT_OPTIONS="100 12 23 space"

CMD [ "/bin/bash", "/docker/boot.sh" ]

# ----------------------------------------------------------------
FROM base AS production
# install simcore packages
COPY --chown=jovyan:users packages/simcore-sdk /packages/simcore-sdk
COPY --chown=jovyan:users packages/s3wrapper /packages/s3wrapper
# copy the default notebook
COPY --chown=jovyan:users services/dy-jupyter/work /home/jovyan/work
RUN pip install /packages/simcore-sdk &&\
    pip install /packages/s3wrapper
ENTRYPOINT [ "/bin/bash", "/docker/boot.sh" ]