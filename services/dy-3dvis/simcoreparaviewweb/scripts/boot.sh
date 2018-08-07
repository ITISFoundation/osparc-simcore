#!/bin/bash
echo "current directory is ${PWD}"

if [[ -v CREATE_DUMMY_TABLE ]];
then
    echo "development mode, creating dummy tables..."
    result="$(python3 devel/devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result node uuid of $result";
    export SIMCORE_NODE_UUID="$result";
    host_name="localhost"
else
    host_name="$(hostname -f)"
fi


echo "modifying apache configuration..."
. scripts/apachePatch.sh

service apache2 restart

echo "Waiting for server port to be defined"
server_port="$(python3 src/getport.py)";

echo "starting paraview using hostname ${host_name} and websocket port $server_port..."
/opt/paraviewweb/scripts/start.sh "ws://osparc01.speag.com:$server_port"
