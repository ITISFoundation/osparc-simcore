# Dynamic services

## Definitions


### legacy dynamic service:
    is managed by the director-v0
    can be 1 or more docker services that can run anywhere in the cluster
### modern dynamic service:
    the service is managed via the dynamic-sidecar by the director-v2
    is composed of at least a dynamic-sidecar that act as a pod controller
    is composed of at least a reverse-proxy that act as the service web entrypoint
    can be 1 or more docker containers that run on the same node as the dynamic-sidecar

## How to determine if a service is legacy or not

*Taken from @sanderegg via https://github.com/ITISFoundation/osparc-simcore/issues/3964#issuecomment-1486300837*

1. list all the services
2. get all the ones containing a docker image label `simcore.service.paths-mapping`, these are modern. Remove them from the list.
3. In the modern services, check for the docker image label `simcore.service.compose-spec`. If it is available, look for the services listed in this docker image label and remove them from original list as well
4. what remains are the legacy services
