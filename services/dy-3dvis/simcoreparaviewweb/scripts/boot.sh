#!/bin/bash
echo "current directory is ${PWD}"

if [[ -v CREATE_DUMMY_TABLE ]];
then
    # in dev mode, data located in mounted volume /test-data are uploaded to the S3 server
    # also a fake configuration is set in the DB to simulate the osparc platform
    echo "development mode, creating dummy tables..."
    result="$(python3 devel/devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result node uuid of $result";
    # the fake SIMCORE_NODE_UUID is exported to be available to the service
    export SIMCORE_NODE_UUID="$result";
    # TODO: host name shall be defined dynamically instead of stupidely hard-coded
    host_name="localhost"
else
    host_name="osparc01.speag.com"
fi

echo "modifying apache configuration..."
. scripts/apachePatch.sh

echo "restarting the apache service..."
service apache2 restart


# the service waits until the calling client transfers the service externally published port
# this is currently necessary due to some unknown reason with regard to how paraviewweb 
# visualizer is started (see below)
echo "Waiting for server port to be defined"
server_port="$(python3 src/getport.py)";

# to start the paraviewweb visualizer it needs as parameter something to do with the way
# its websockets are setup "ws://HOSTNAME:PORT" hostname and port must be the hostname and port
# as seen from the client side (if in local development mode, this would be typically localhost and 
# whatever port is being published outside the docker container)
echo "starting paraview using hostname ${host_name} and websocket port $server_port..."
/opt/paraviewweb/scripts/start.sh "ws://${host_name}:$server_port"
