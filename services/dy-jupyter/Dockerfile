ARG BASE_IMAGE=jupyter/base-notebook
FROM ${BASE_IMAGE}  AS base

LABEL maintainer="sanderegg"
EXPOSE 8888
# ----------------------------------------------------------------
# Add a python2 kernel in the notebook
# Create a Python 2.x environment using conda including at least the ipython kernel
# and the kernda utility. Add any additional packages you want available for use
# in a Python 2 notebook to the first line here (e.g., pandas, matplotlib, etc.)
ARG INSTALL_PYTHON2
RUN if [ "x${INSTALL_PYTHON2}" = "1" ] ; then conda create --quiet --yes -p $CONDA_DIR/envs/python2 python=2.7 ipython ipykernel kernda && \
    conda clean -tipsy ; fi
USER root
# Create a global kernelspec in the image and modify it so that it properly activates
# the python2 conda environment.
RUN if [ "x${INSTALL_PYTHON2}" = "1" ] ; then $CONDA_DIR/envs/python2/bin/python -m ipykernel install && \
$CONDA_DIR/envs/python2/bin/kernda -o -y /usr/local/share/jupyter/kernels/python2/kernel.json ; fi
USER $NB_USER
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
# ----------------------------------------------------------------
COPY --chown=jovyan:users scripts/docker/healthcheck_curl_host.py /healthcheck/healthcheck_curl_host.py
# will start to run after interval every interval. fails after timeout. fail do not count if during start-period. will do # retries
HEALTHCHECK --interval=10s --timeout=30s --start-period=1s --retries=3 CMD [ "python3", "/healthcheck/healthcheck_curl_host.py", "http://localhost:8888" ]
# configure notebook
RUN pip install --upgrade pip && \
    pip install jupyter_contrib_nbextensions && \
    pip install jupyterthemes && \
    jt -t oceans16 -T -N -kl && \
    jupyter contrib nbextensions install --user && \
    jupyter nbextension enable hide_input/main && \
    jupyter nbextension enable init_cell/main
# ----------------------------------------------------------------
ENV PYTHONPATH=/home/jovyan/handlers
COPY --chown=jovyan:users services/dy-jupyter/notebook-customisation/custom.js /home/jovyan/.jupyter/custom/custom.js

ENV NOTEBOOK_URL="notebooks/notebook.ipynb"
# ----------------------------------------------------------------
FROM base AS development
VOLUME /home/jovyan/packages
VOLUME /home/jovyan/services
VOLUME /home/jovyan/devel
VOLUME /home/root/scripts/dy_services_helpers
VOLUME /home/jovyan/docker
VOLUME /home/jovyan/handlers
# increase development speed by pre-installing libraries
COPY --chown=jovyan:users services/dy-jupyter/devel/requirements.txt /home/jovyan/devel/requirements.txt
RUN pip install -r /home/jovyan/devel/requirements.txt
ENV CREATE_DUMMY_TABLE=1
ENV USE_CASE_CONFIG_FILE="devel/port_config.json"
ENV INIT_OPTIONS="100 12 23 space"

CMD [ "/bin/bash", "/docker/boot.sh" ]

# ----------------------------------------------------------------
FROM base AS production
# prepare for booting
COPY --chown=jovyan:users services/dy-jupyter/docker /docker
# install simcore packages. docker seems to set root:root permission to the implicitely created destination folders
COPY --chown=jovyan:users packages/simcore-sdk /home/jovyan/packages/simcore-sdk
COPY --chown=jovyan:users packages/s3wrapper /home/jovyan/packages/s3wrapper
COPY --chown=jovyan:users services/storage/client-sdk /home/jovyan/services/storage/client-sdk
COPY --chown=jovyan:users services/dy-jupyter/handlers/input_retriever.py /home/jovyan/handlers/input_retriever.py
USER root
RUN chown -R jovyan:users /home/jovyan/packages && \
    chown -R jovyan:users /home/jovyan/services
USER $NB_USER
# copy the default notebook
COPY --chown=jovyan:users services/dy-jupyter/notebooks /home/jovyan/notebooks
RUN pip install /home/jovyan/packages/s3wrapper && \
    pip install /home/jovyan/services/storage/client-sdk/python && \
    pip install /home/jovyan/packages/simcore-sdk    
# cleanup    
RUN rm -rf /home/jovyan/packages && \
    rm -rf /home/jovyan/services
ENTRYPOINT [ "/bin/bash", "/docker/boot.sh" ]
