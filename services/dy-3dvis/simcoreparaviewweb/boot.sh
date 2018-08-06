#!/bin/bash
echo "current directory is ${PWD}"

if [[ -v CREATE_DUMMY_TABLE ]];
then
    echo "development mode, creating dummy tables..."
    result="$(python3 devel-initconfiguration.py ${USE_CASE_CONFIG_FILE})";
    echo "Received result node uuid of $result";
    export SIMCORE_NODE_UUID="$result";
fi

/opt/paraviewweb/scripts/addEndpoints.sh "retrieve" "/home/root"
echo "modifying apache configuration..."
sed -i '34 i\Options +ExecCGI' /etc/apache2/sites-available/001-pvw.conf
sed -i '35 i\AddHandler cgi-script .py' /etc/apache2/sites-available/001-pvw.conf
a2enmod cgid
mkdir /data
chmod 777 /data

echo "retrieving data from S3..."
python3 "input-retriever.py";
echo "starting paraview using websocket port $SERVER_PORT..."
/opt/paraviewweb/scripts/start.sh "ws://localhost:$SERVER_PORT" --mesa-llvm