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
LABEL org.label-schema.name="simcore/services/2d-analysis"
LABEL org.label-schema.description="2D table/graph analysis"
LABEL org.label-schema.url="http://jupyter.org/"
LABEL org.label-schema.vcs-url="https://github.com/jupyter/docker-stacks"
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.vendor="IT'IS foundation"
LABEL org.label-schema.version=$BUILD_VERSION
LABEL org.label-schema.docker.cmd="docker run -it --rm -p 8888:8888 jupyter/base-notebook start-notebook.sh --NotebookApp.token=''"
# service runtime settings
LABEL simcore.service.settings='[{"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}]'

# install the plotly, pandas, the jupyter extensions
RUN pip install plotly \
    pandas \
    jupyter_contrib_nbextensions \
    jupyter_dashboards && \
    jupyter contrib nbextensions install --user && \
    jupyter dashboards quick-setup --sys-prefix && \    
    jupyter nbextension enable hide_input/main
COPY --chown=jovyan:users plotly.ipynb .
COPY --chown=jovyan:users /simcore_api ./simcore_api

# define where the inputs shall be defined
VOLUME /home/jovyan/data
VOLUME /home/jovyan/config

# starts notebook without token
CMD [ "start-notebook.sh", "--NotebookApp.token=''", "--NotebookApp.tornado_settings={\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}", "--NotebookApp.default_url=/notebooks/plotly.ipynb" ]
