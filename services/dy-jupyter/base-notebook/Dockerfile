# FIXME: add tag with concrete version!
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

COPY --chown=jovyan:users osparc-demo.ipynb .

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

# starts notebook without token
CMD [ "start-notebook.sh", "--NotebookApp.token=''", "--NotebookApp.tornado_settings={\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}" ]
