# Workbench-backend: Provide access to services from docker registry


Overview
========

Workbench-backend is a first draft of the architecture that shall provide clients with interactive services available in the docker registry. It allows for listing, starting and stopping simcore services. These simcore services may be composed of 1 to N docker images. The workbench-backend shall automatically connect these docker container as needed.


Architecture
 ===========
 - light-weight workbench client/server (using python aiohttp,requests)
 - director (using python flask, docker, requests)
 - docker registry (on masu computer)

Workflow
 =======
 1. Get list of available services (returns their name)
 2. Define a _uuid_ and start a service using one of the names returned in 1.
 3. After the service is started its published port(s) are returned and may be used to browse to. The service own webserver will serve at this location.
 4. Using the service uuid the service may be stopped.

 Building Services
 =================
To build the workbench-backend, the computer must be part of a swarm.

<code>
$ docker swarm init
$ docker-compose up
</code>