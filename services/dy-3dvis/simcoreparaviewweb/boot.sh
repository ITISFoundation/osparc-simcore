#!/bin/bash
echo "current directory is ${PWD}"

if [[ -v CREATE_DUMMY_TABLE ]];
then
    echo "development mode, creating dummy tables..."
    result="$(python3 devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result node uuid of $result";
    export SIMCORE_NODE_UUID="$result";
fi

echo "retrieving data from S3..."
python3 "input-retriever.py";
#./startup.sh;
echo "starting nginx..."
service nginx start

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib/paraview-$PV_VERSION_MAJOR/:/usr/local/lib/

Visualizer --paraview /usr/local/lib/paraview-$PV_VERSION_MAJOR/ \
        --data /home/scu/input \
        --port 9777 \
        --server-only