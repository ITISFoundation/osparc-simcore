#!/bin/sh

if [[ ${CREATE_DUMMY_TABLE} == "1" ]]
then
    echo "Creating dummy tables ..."
    exec python ./packages/packages/simcore-sdk/src/simcore_sdk/nodeports/__dbdevel.py
fi

start-notebook.sh \
    --NotebookApp.token='' \
    --NotebookApp.tornado_settings="{\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}" \
    --NotebookApp.default_url=/notebooks/${NOTEBOOK_URL}