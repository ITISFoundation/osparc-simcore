ARG BASE_IMAGE=jupyter/base-notebook
FROM ${BASE_IMAGE}

LABEL maintainer="sanderegg"

ENV SIMCORE_NODE_UUID="-1" \
    S3_ENDPOINT="=1" \
    S3_ACCESS_KEY="-1" \
    S3_SECRET_KEY="-1" \
    S3_BUCKET_NAME="-1" \
    POSTGRES_ENDPOINT="-1" \
    POSTGRES_USER="-1" \
    POSTGRES_PASSWORD="-1" \
    POSTGRES_DB="-1"

EXPOSE 8888

LABEL io.simcore.key='{"key": "simcore/services/jupyter-base-notebook"}' \
        io.simcore.tag='{"tag": "${SERVICES_VERSION}"}' \
        io.simcore.name='{"name": "jupyter-base-notebook"}' \
        io.simcore.description='{"description": "Jupyter notebook using base docker image"}' \
        io.simcore.contact='{"contact": "anderegg@itis.swiss"}' \
        io.simcore.authors='{"authors": [{"name": "sanderegg", "email": ""anderegg@itis.swiss"", "affiliation": "ITIS Foundation"}]}' \
        io.simcore.inputs='{"inputs": []}' \
        io.simcore.outputs='{"outputs": []}' \
        io.simcore.viewer='{"viewer":{"ip":null, "port":null}}' \
        simcore.service.settings='[{"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}]' \
        org.label-schema.url='http://jupyter.org/' \
        org.label-schema.vcs-url='https://github.com/jupyter/docker-stacks' \
        org.label-schema.schema-version="1.0" \
        org.label-schema.build-date="${BUILD_DATE}" \
        org.label-schema.vcs-ref="${VCS_REF}"

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
