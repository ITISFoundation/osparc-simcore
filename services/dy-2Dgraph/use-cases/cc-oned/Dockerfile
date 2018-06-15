FROM simcore/services/jupyter-base-notebook:latest

LABEL maintainer="sanderegg"

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

# install git
USER root
RUN apt-get update && \
    apt-get install -y git
USER $NB_USER

# install the plotly, pandas, the jupyter extensions
RUN pip install plotly \
    pandas \
    jupyter_contrib_nbextensions \
    jupyter_dashboards && \
    jupyter contrib nbextensions install --user && \
    jupyter dashboards quick-setup --sys-prefix && \    
    jupyter nbextension enable hide_input/main && \
    jupyter nbextension enable init_cell/main

ARG NOTEBOOK_NAME=cc_oned.ipynb
COPY --chown=jovyan:users ${NOTEBOOK_NAME} .
RUN jupyter trust ${NOTEBOOK_NAME}

# download the simcore_sdk pacakge
RUN git clone https://github.com/sanderegg/osparc-simcore.git --branch analysis_2d_graph  ./packages
ENV PYTHONPATH=./packages/packages/simcore-sdk/src

# define where the inputs shall be defined
VOLUME /home/jovyan/data
VOLUME /home/jovyan/config

COPY --chown=jovyan:users boot.sh boot.sh
RUN chmod +x boot.sh

# starts notebook without token
ENV NOTEBOOK_URL=${NOTEBOOK_NAME}

CMD [ "/bin/sh", "boot.sh" ]
#CMD echo ${NOTEBOOK_URL}
#CMD [ "start-notebook.sh", \
#    "--NotebookApp.token=''", \ 
#    "--NotebookApp.tornado_settings={\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}", \
#    "--NotebookApp.default_url=/notebooks/${NOTEBOOK_URL}"]