# Simcore - paraviewweb service

This service is based on the official docker images [dockerhub](https://hub.docker.com/r/kitware/paraviewweb/).

It brings the paraview visualizer application as an example of how easy one can integrate external tools in the osparc platform.

## local development

1. go to /services/dy-3dvis/simcoreparaviewweb/
2. execute `make build-devel`, this will build the service as "development" code together with a local minio S3 storage and a postgres DB
3. execute `make up-devel`, this will run the service locally
4. open a terminal (preferably bash)
5. Not necessary in dev mode anymore as it is done automatically: execute `curl -i -X POST localhost:8777/setport -d "port=8777" -d "hostname=localhost"` in the terminal (this will start the paraviewweb visualizer app)
6. execute `curl -i -X POST localhost:8777/visualizer/retrieve` in the terminal (this will make the simcore paraviewweb download the data from the local S3 storage)
7. open browser at [localhost:8777/visualizer](localhost:8777/visualizer)

## production

1. go to /service/dy-3dvis/simcoreparaviewweb/
2. execute `make build`, this build the service as "production" code
3. in the __Makefile__ change the version of __SERVICES_VERSION__ accordingly
4. execute `make push_service_images`, this will upload the created docker images to the registry