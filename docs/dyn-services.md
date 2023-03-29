# Dynamic services

## How to determine if a service is legacy or not

*Taken from @sanderegg via https://github.com/ITISFoundation/osparc-simcore/issues/3964#issuecomment-1486300837*

1. list all the services
2. get all the ones containing a docker image label `simcore.service.paths-mapping`, these are modern. Remove them from the list.
3. In the modern services, check for the docker image label `simcore.service.compose-spec`. If it is available, look for the services listed in this docker image label and remove them from original list as well
4. what remains are the legacy services
