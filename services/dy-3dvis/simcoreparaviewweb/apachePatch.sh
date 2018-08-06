#!/usr/bin/env bash

echo "enable CGI"
sed -i '34 i\Options +ExecCGI' /etc/apache2/sites-available/001-pvw.conf
sed -i '35 i\AddHandler cgi-script .py' /etc/apache2/sites-available/001-pvw.conf

echo "copy env variables"
sed -i '12 i\. /etc/environment' /etc/apache2/envvars

echo "export PYTHONPATH=/home/root/packages/packages/simcore-sdk/src:/home/root/packages/packages/s3wrapper/src" >> /etc/environment
sed -i '5 i\SetEnv PYTHONPATH ${PYTHONPATH}' /etc/apache2/sites-available/001-pvw.conf

echo "export SIMCORE_NODE_UUID=${SIMCORE_NODE_UUID}" >> /etc/environment
sed -i '5 i\SetEnv SIMCORE_NODE_UUID ${SIMCORE_NODE_UUID}' /etc/apache2/sites-available/001-pvw.conf

echo "export S3_ENDPOINT=${S3_ENDPOINT}" >> /etc/environment
sed -i '5 i\SetEnv S3_ENDPOINT ${S3_ENDPOINT}' /etc/apache2/sites-available/001-pvw.conf

echo "export S3_ACCESS_KEY=${S3_ACCESS_KEY}" >> /etc/environment
sed -i '5 i\SetEnv S3_ACCESS_KEY ${S3_ACCESS_KEY}' /etc/apache2/sites-available/001-pvw.conf

echo "export S3_SECRET_KEY=${S3_SECRET_KEY}" >> /etc/environment
sed -i '5 i\SetEnv S3_SECRET_KEY ${S3_SECRET_KEY}' /etc/apache2/sites-available/001-pvw.conf

echo "export S3_BUCKET_NAME=${S3_BUCKET_NAME}" >> /etc/environment
sed -i '5 i\SetEnv S3_BUCKET_NAME ${S3_BUCKET_NAME}' /etc/apache2/sites-available/001-pvw.conf

echo "export POSTGRES_ENDPOINT=${POSTGRES_ENDPOINT}" >> /etc/environment
sed -i '5 i\SetEnv POSTGRES_ENDPOINT ${POSTGRES_ENDPOINT}' /etc/apache2/sites-available/001-pvw.conf

echo "export POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" >> /etc/environment
sed -i '5 i\SetEnv POSTGRES_PASSWORD ${POSTGRES_PASSWORD}' /etc/apache2/sites-available/001-pvw.conf

echo "export POSTGRES_USER=${POSTGRES_USER}" >> /etc/environment
sed -i '5 i\SetEnv POSTGRES_USER ${POSTGRES_USER}' /etc/apache2/sites-available/001-pvw.conf

echo "export POSTGRES_DB=${POSTGRES_DB}" >> /etc/environment
sed -i '5 i\SetEnv POSTGRES_DB ${POSTGRES_DB}' /etc/apache2/sites-available/001-pvw.conf

echo ${PARAVIEW_INPUT_PATH}
echo "export PARAVIEW_INPUT_PATH=${PARAVIEW_INPUT_PATH}" >> /etc/environment
sed -i '5 i\SetEnv PARAVIEW_INPUT_PATH ${PARAVIEW_INPUT_PATH}' /etc/apache2/sites-available/001-pvw.conf

a2enmod cgid
mkdir /data
chmod 777 /data/

