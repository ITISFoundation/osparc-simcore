#!/bin/bash

if test "${CREATE_DUMMY_TABLE}" = "1"
then
    pip install -r /home/jovyan/devel/requirements.txt
    pushd /home/jovyan/packages/simcore-sdk; pip install -r requirements-dev.txt; popd
    pushd /home/jovyan/packages/s3wrapper; pip install -r requirements-dev.txt; popd

    echo "Creating dummy tables ... using ${USE_CASE_CONFIG_FILE}"
    result="$(python devel/initialise_dummy_platform.py ${USE_CASE_CONFIG_FILE} ${INIT_OPTIONS})"
    echo "Received result of $result";
    IFS=, read -a array <<< "$result"; 
    echo "Received result pipeline id of ${array[0]}";
    echo "Received result node uuid of ${array[1]}";
    # the fake SIMCORE_NODE_UUID is exported to be available to the service
    export SIMCORE_NODE_UUID="${array[1]}";
fi

jupyter trust ${NOTEBOOK_URL}
start-notebook.sh \
    --NotebookApp.notebook_dir='/home/jovyan/notebooks' \
    --NotebookApp.token='' \
    --NotebookApp.tornado_settings="{\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}" \
    # --NotebookApp.default_url='/notebooks' \
    
