#!/bin/bash
echo "current directory is ${PWD}"

if [[ -v CREATE_DUMMY_TABLE ]];
then
    echo "development mode, creating dummy tables..."
    result="$(python3 devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result node uuid of $result";
    export SIMCORE_NODE_UUID="$result";
fi


python3 "input-retriever.py";
./startup.sh;