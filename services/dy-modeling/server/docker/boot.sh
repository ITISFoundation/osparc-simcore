#!/bin/bash
echo "current directory is ${PWD}"

# we need to be in python 3.6 to install simcore stuff
export PATH="${PYENV_ROOT}/bin:$PATH"
eval "$(pyenv init -)"
python -V
pip -V

if [[ -v CREATE_DUMMY_TABLE ]];
then
    pushd /home/node/packages/simcore-sdk; pip3 install -r requirements-dev.txt; popd
    pushd /home/node/packages/s3wrapper; pip3 install -r requirements-dev.txt; popd
    pushd /home/node/scripts/dy_services_helpers; pip3 install -r requirements.txt; popd
    # in dev mode, data located in mounted volume /test-data are uploaded to the S3 server
    # also a fake configuration is set in the DB to simulate the osparc platform
    echo "development mode, creating config..."
    # in style: pipelineid,nodeuuid
    result="$(python3 scripts/dy_services_helpers/platform_initialiser.py ${USE_CASE_CONFIG_FILE} --folder ${TEST_DATA_PATH})";
    echo "Received result of $result";
    IFS=, read -a array <<< "$result"; 
    echo "Received result pipeline id of ${array[0]}";
    echo "Received result node uuid of ${array[1]}";
    # the fake SIMCORE_NODE_UUID is exported to be available to the service
    export SIMCORE_NODE_UUID="${array[1]}";

    nodemon -L start
else
    npm start
fi

