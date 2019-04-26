#!/bin/bash

set -e

# try to pull data from S3
python /docker/state_puller.py ${SIMCORE_NODE_APP_STATE_PATH} --silent

# the notebooks in the folder shall be trusted by default
jupyter trust ${SIMCORE_NODE_APP_STATE_PATH}/*

# call the notebook with the basic parameters
start-notebook.sh \
    --NotebookApp.base_url=${SIMCORE_NODE_BASEPATH} \
    --NotebookApp.extra_static_paths="['${SIMCORE_NODE_BASEPATH}/static']" \
    --NotebookApp.notebook_dir=${SIMCORE_NODE_APP_STATE_PATH} \
    --NotebookApp.token=""  \
    --NotebookApp.disable_check_xsrf='True' \
    --NotebookApp.quit_button='False' \
    --NotebookApp.webbrowser_open_new='0' \
    --NotebookApp.nbserver_extensions="{'input_retriever':True, 'state_handler':True}" \
    --FileContentsManager.post_save_hook='post_save_hook.export_to_osparc_hook' \
    "$@"
    # --Session.debug='True'
    # --NotebookApp.token="${NOTEBOOK_TOKEN}" \ this should replace no token and disable_check_xsrf but it currently does not work in platform (reverse proxy?)
