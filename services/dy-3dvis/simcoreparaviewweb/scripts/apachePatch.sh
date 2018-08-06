#!/usr/bin/env bash

echo "copy env variables"
sed -i '12 i\. /etc/environment' /etc/apache2/envvars

echo "export PYTHONPATH=/home/root/packages/packages/simcore-sdk/src:/home/root/packages/packages/s3wrapper/src" >> /etc/environment
echo "export SIMCORE_NODE_UUID=${SIMCORE_NODE_UUID}" >> /etc/environment
echo "export S3_ENDPOINT=${S3_ENDPOINT}" >> /etc/environment
echo "export S3_ACCESS_KEY=${S3_ACCESS_KEY}" >> /etc/environment
echo "export S3_SECRET_KEY=${S3_SECRET_KEY}" >> /etc/environment
echo "export S3_BUCKET_NAME=${S3_BUCKET_NAME}" >> /etc/environment
echo "export POSTGRES_ENDPOINT=${POSTGRES_ENDPOINT}" >> /etc/environment
echo "export POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" >> /etc/environment
echo "export POSTGRES_USER=${POSTGRES_USER}" >> /etc/environment
echo "export POSTGRES_DB=${POSTGRES_DB}" >> /etc/environment
echo "export PARAVIEW_INPUT_PATH=${PARAVIEW_INPUT_PATH}" >> /etc/environment

echo "add aliases and script execution"
sed -i -e '/CustomLog/r config/apache.conf' /etc/apache2/sites-available/001-pvw.conf

a2enmod cgid
mkdir /data
chmod 777 /data/

