FROM masu.speag.com/simcore/services/jupyter-base-notebook:1.4.0 AS common
LABEL maintainer="sanderegg"

# install ffmpeg --------------------------------------------------------------
USER root
RUN apt-get update && \
    apt-get install -y \
    ffmpeg
USER $NB_USER

# install requirements, apply theme -------------------------------------------
COPY --chown=jovyan:users cc/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \    
    jt -t oceans16
# prepare for booting ---------------------------------------------------------
COPY --chown=jovyan:users docker /docker
# set of arguments to copy the right notebook ---------------------------------
ARG NOTEBOOK_NAME
ENV NOTEBOOK_URL=${NOTEBOOK_NAME}
# -----------------------------------------------------------------------------
FROM common AS development
VOLUME /packages
VOLUME /home/jovyan/devel
VOLUME /home/jovyan/devel-config
VOLUME /home/jovyan/notebook
ENV USE_CASE_CONFIG_FILE="node_configuration_file.json"
ENV CREATE_DUMMY_TABLE=1
ENTRYPOINT []
CMD [ "/bin/bash", "/docker/boot.sh" ]
# -----------------------------------------------------------------------------
FROM common AS production
# set of arguments to copy the right notebook
ARG NOTEBOOK_NAME
ARG NOTEBOOK_FOLDER_NAME
# copy the notebook in the image
COPY --chown=jovyan:users cc/${NOTEBOOK_FOLDER_NAME}/${NOTEBOOK_NAME} ${NOTEBOOK_NAME}
ENTRYPOINT [ "/bin/bash", "/docker/boot.sh" ]