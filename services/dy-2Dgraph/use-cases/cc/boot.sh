#!/bin/sh

if test "${CREATE_DUMMY_TABLE}" = "1"
then
    echo "Creating dummy tables ..."
    python develdbs3init.py
fi

start-notebook.sh \
    --NotebookApp.token='' \
    --NotebookApp.tornado_settings="{\"headers\":{\"Content-Security-Policy\":\"frame-ancestors+'self'+http://osparc01.speag.com:9081;+report-uri/api/security/csp-report\"}}" \
    --NotebookApp.default_url=/notebooks/${NOTEBOOK_URL}