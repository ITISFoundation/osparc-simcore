#!/bin/bash
echo "current directory is ${PWD}"

if [[ -v CREATE_DUMMY_TABLE ]];
then
    echo "development mode, creating dummy tables..."
    result="$(python3 devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result node uuid of $result";
    export SIMCORE_NODE_UUID="$result";
fi

#TODO: set a shell script to call the script
echo "setting additional endpoints..."
/opt/paraviewweb/scripts/addEndpoints.sh "setport" "/home/root/setport.py"
/opt/paraviewweb/scripts/addEndpoints.sh "retrieve" "/home/root/input-retriever.py"
echo "modifying apache configuration..."
. ./apachePatch.sh

echo "Waiting for server port to be defined"
server_port="$(python3 external-port-retriever.py)";
echo "starting paraview using websocket port $server_port..."
/opt/paraviewweb/scripts/start.sh "ws://localhost:$server_port"
