#!/bin/bash
echo "current directory is ${PWD}"



if [[ -v CREATE_DUMMY_TABLE ]];
then
    pushd /home/root/packages/simcore-sdk; pip install -r requirements-dev.txt; popd
    pushd /home/root/packages/s3wrapper; pip install -r requirements-dev.txt; popd
    # in dev mode, data located in mounted volume /test-data are uploaded to the S3 server
    # also a fake configuration is set in the DB to simulate the osparc platform
    echo "development mode, creating dummy tables..."
    # in style: pipelineid,nodeuuid
    result="$(python3 devel/devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result of $result";
    IFS=, read -a array <<< "$result"; 
    echo "Received result pipeline id of ${array[0]}";
    echo "Received result node uuid of ${array[1]}";
    # the fake SIMCORE_NODE_UUID is exported to be available to the service
    export SIMCORE_PIPELINE_ID="${array[0]}";
    export SIMCORE_NODE_UUID="${array[1]}";
fi

echo "modifying apache configuration..."
. scripts/apachePatch.sh

echo "restarting the apache service..."
service apache2 restart

# echo "modifying wslink launcher configuration"
. scripts/visualizer_launcher_patch.sh

if [[ -v CREATE_DUMMY_TABLE ]];
then
    # in dev mode we know already what the host/port are
    host_name=${HOST_NAME}
    server_port=${SERVER_PORT}    
else
    # the service waits until the calling client transfers the service externally published port/hostname
    # this is currently necessary due to some unknown reason with regard to how paraviewweb 
    # visualizer is started (see below)
    echo "Waiting for server hostname/port to be defined"
    host_port="$(python3 src/getport.py)";
    echo "Received hostname/port: ${host_port}"
    IFS=, read -a array <<< "$host_port"; 
    echo "Host name decoded as ${array[0]}";
    echo "Port decoded as ${array[1]}";
    host_name=${array[0]}
    server_port=${array[1]}
fi


# to start the paraviewweb visualizer it needs as parameter something to do with the way
# its websockets are setup "ws://HOSTNAME:PORT" hostname and port must be the hostname and port
# as seen from the client side (if in local development mode, this would be typically localhost and 
# whatever port is being published outside the docker container)
echo "starting paraview using hostname ${host_name} and websocket port $server_port..."
/opt/paraviewweb/scripts/start.sh "ws://${host_name}:$server_port"
