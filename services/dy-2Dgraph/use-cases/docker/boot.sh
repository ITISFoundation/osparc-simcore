#!/bin/bash

if test "${CREATE_DUMMY_TABLE}" = "1"
then
    pip install -r /home/jovyan/devel/requirements.txt
    pushd /packages/simcore-sdk; pip install -r requirements-dev.txt; popd
    pushd /packages/s3wrapper; pip install -r requirements-dev.txt; popd

    echo "Creating dummy tables ... using ${USE_CASE_CONFIG_FILE}"
    result="$(python devel/initialise_dummy_platorm.py ${USE_CASE_CONFIG_FILE} ${INIT_OPTIONS})"
    echo "Received result node uuid of $result"
    export SIMCORE_NODE_UUID="$result"
fi

jupyter trust ${NOTEBOOK_URL}
start-notebook.sh \
    --NotebookApp.token='' \
    --NotebookApp.tornado_settings="{\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}" \
    --NotebookApp.default_url=/notebooks/${NOTEBOOK_URL}