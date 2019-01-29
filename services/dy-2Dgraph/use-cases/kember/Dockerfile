ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS common
LABEL maintainer="sanderegg"

# install requirements --------------------------------------------------------
COPY --chown=jovyan:users kember/requirements.txt .
# TODO: tmp workaround for https://github.com/pypa/pip/issues/6197
RUN pip --cache-dir=/pipcache install -r requirements.txt &&\
    rm -rf /pipcache


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
ENV INIT_OPTIONS="100 6000 20 space"
ENV CREATE_DUMMY_TABLE=1
# switch off the default entrypoint
ENTRYPOINT []
CMD [ "/bin/bash", "/docker/boot.sh" ]
# -----------------------------------------------------------------------------
FROM common AS production
# set of arguments to copy the right notebook
ARG NOTEBOOK_NAME
# copy the notebook in the image
COPY --chown=jovyan:users kember/${NOTEBOOK_NAME} ${NOTEBOOK_NAME}
ENTRYPOINT [ "/bin/bash", "/docker/boot.sh" ]
