#!/bin/bash
echo "current directory is ${PWD}"

if [[ -v CREATE_DUMMY_TABLE ]];
then
    echo "development mode, creating dummy tables..."
    result="$(python3 devel/devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result node uuid of $result";
    export SIMCORE_NODE_UUID="$result";
fi

echo "modifying apache configuration..."
. scripts/apachePatch.sh

service apache2 restart

echo "Waiting for server port to be defined"
server_port="$(python3 src/getport.py)";
echo "starting paraview using websocket port $server_port..."
/opt/paraviewweb/scripts/start.sh "ws://localhost:$server_port"
