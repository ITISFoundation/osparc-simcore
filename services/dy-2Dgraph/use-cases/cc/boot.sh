#!/bin/sh

if test "${CREATE_DUMMY_TABLE}" = "1"
then
    echo "Creating dummy tables ... using ${USE_CASE_CONFIG_FILE}"
    result="$(python develdbs3init.py ${USE_CASE_CONFIG_FILE})"
    echo "Received result node uuid of $result"
    export SIMCORE_NODE_UUID="$result"
fi

start-notebook.sh \
    --NotebookApp.token='' \
    --NotebookApp.tornado_settings="{\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}" \
    --NotebookApp.default_url=/notebooks/${NOTEBOOK_URL}