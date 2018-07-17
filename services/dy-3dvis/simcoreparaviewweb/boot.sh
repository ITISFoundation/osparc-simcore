#!/bin/bash
echo "current directory is ${PWD}"

if [-z "${CREATE_DUMMY_TABLE+x}"]
then
    echo "development mode, creating dummy tables"
    result="$(python develdbs3init.py ${USE_CASE_CONFIG_FILE})"
    echo "Received result node uuid of $result"
    export SIMCORE_NODE_UUID="$result"
fi


python3 "input-retriever.py"
startup.sh