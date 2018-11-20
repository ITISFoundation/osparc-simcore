# Simcore - Jupyter Notebook service

This service is based on the official docker images [dockerhub](https://hub.docker.com/r/jupyter/base-notebook/).

It brings the jupyter notebook application as an example of how easy one can integrate external tools in the osparc platform.

## local development

1. go to /services/dy-jupyter/
2. execute `make build-devel`, this will build the service as "development" code together with a local minio S3 storage and a postgres DB
3. execute `make up-devel`, this will run the service locally
4. open browser at [localhost:8888](localhost:8888)

## production

1. go to /service/dy-jupyter/
2. execute `make build`, this build the service as "production" code
3. in the __Makefile__ change the version of __SERVICES_VERSION__ accordingly
4. execute `make push_service_images`, this will upload the created docker images to the registry