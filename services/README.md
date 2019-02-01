# services

Each folder contains a services that is part or can be spawned by the platform.
The prefix *dy-* in the naming indicates that this service is not a building
part of the application (i.e. not listed as an services in the docker-compose file)
but instead it is *dy*namically spawned by the director as a back-end service.

## overview

This is a schematic of how services are interconnected:

[![service-web](../docs/img/service-web.svg)](http://interactive.blockdiag.com/?compression=deflate&src=eJxdjs0KwjAQhO99imXPFtNbpcYXkR7ys2hw6UqSKiK-uymxiF7nm28Yy-IuPpgTPBsAvJPdOg40ZYRjOpsr6UkyjUOB_tEmirfgKH0YaEDHMnsshX993x5qsEgUyx4bS6x3qu824IQlastz3f4pFtGHSC5LXCXsleqw3ljRUvteGprXG1PtQR0)

and here follows a quick description of each service.

### authentication

User login/authentication service...

### computation

Computational services...

### director

The director is responsible for making dynamic services and computational services available in a docker registry to the workbench application.
It is also responsible for starting and stopping such a service on demand. A service may be composed of 1 to N connected docker images.

### jupyter

This is a third party service based on jupyter notebook images. It brings the jupyter notebook in the osparc workbench.

### modeling

This is a service providing 3D modeling capabilities.

### web

This is a service that provides the server/client infrastructure of the the workbench application.

## Architecture

### workbench

The association of the web, authentication and director services creates the so-called workbench application. It provides the main entry point for the user.

### workbench nodes

The other services are made available through a docker registry to the workbench application.
When a node is created in the workbench frontend, the director starts the respective services accordingly.
The started services are dispatched on the available cluster and connected to the workbench application.
When the user closes a node or disconnects, any running service will be automatically closed.

## Development Workflow

To build images for development

```!bash
  make build-devel
  make up-devel
```

To build images for production (w/o tagging)

```!bash
  make build
  make up
```

## Deploying Services

To build and tag these images:

```!bash
  make build
```

To deploy the application in a single-node swarm

```!bash
  make up-swarm
```
## Credentials

Rename `.env-devel` to `.env` in order to get the stack up and running.
