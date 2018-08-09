#!/usr/bin/env bash

# in order to access env variables in apache cgi scripts they need to be explicitely added
# also cgi scripts are run as www-data user in Ubuntu (from apache2 specs), meaning the env
# variables must be available to all users.

# to this end one needs to modify /etc/environment to define system wide variables using the 
# docker defined variables (which are user variables)

echo "setting up system-variables..."
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

# to make the variables available to apache the file /etc/apache2/envvars shall contain . /etc/environment
echo "copy env variables"
sed -i '12 i\. /etc/environment' /etc/apache2/envvars

# add the specific configuration necessary to access the scripts through aliases
echo "add aliases and script execution"
sed -i -e '/CustomLog/r config/apache.conf' /etc/apache2/sites-available/001-pvw.conf

# configure apache to use "dynamic content" (https://httpd.apache.org/docs/2.4/howto/cgi.html)
a2enmod cgid
# create a folder accessible by any user inside the docker container where paraview loads its data from (default /data)
mkdir /data
chmod 777 /data/
