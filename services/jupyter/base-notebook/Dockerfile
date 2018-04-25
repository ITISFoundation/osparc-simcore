FROM jupyter/base-notebook
LABEL maintainer="sanderegg"

# call date -u +”%Y-%m-%dT%H:%M:%SZ” in a bash
ARG VCS_REF
ARG BUILD_DATE
# call git rev-parse — short HEAD in a bash
ARG BUILD_VERSION

# Labels.
LABEL org.label-schema.schema-version="1.0"
LABEL org.label-schema.build-date=$BUILD_DATE
LABEL org.label-schema.name="simcore/services/base-notebook"
LABEL org.label-schema.description="Jupyter base-notebook"
LABEL org.label-schema.url="http://jupyter.org/"
LABEL org.label-schema.vcs-url="https://github.com/jupyter/docker-stacks"
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.vendor="IT'IS foundation"
LABEL org.label-schema.version=$BUILD_VERSION
LABEL org.label-schema.docker.cmd="docker run -it --rm -p 8888:8888 jupyter/base-notebook start-notebook.sh --NotebookApp.token=''"
# service runtime settings
LABEL simcore.service.settings='[{"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}]'

# TODO san: this is probably not wise
# starts notebook without token
CMD [ "start-notebook.sh", "--NotebookApp.token=''" ]
