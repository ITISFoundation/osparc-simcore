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

A service is modern if its docker image carries the `simcore.service.paths-mapping`
label; everything else is legacy. If the modern service also carries a
`simcore.service.compose-spec` label, the services listed there are its sidecar
containers, not standalone services in their own right.

At runtime, a running modern service can also be spotted by its docker service
name matching `dy[-_]sidecar.+` (e.g. `dy-sidecar_<node-uuid>`), since only
modern services are wrapped by a dynamic-sidecar.

## CPU/RAM resource allocation

A dynamic service is made of 1 to N docker containers with reservations/limits
defined. Depending on whether the product charges credits for compute
([`_projects_service.py`](../services/web/server/src/simcore_service_webserver/projects/_projects_service.py),
"Get wallet/pricing/hardware information" block), one of the two flows below
applies per project/node.

### Billable

- As a user I have a service made of 1 or X containers that have some
  reservations/limits defined
  ([`get_project_node_resources()`](../services/web/server/src/simcore_service_webserver/projects/_projects_service.py#L2185)).
- As a user I define a pricing plan, which defines an EC2 with some resources
  ([`update_project_node_resources_from_hardware_info()`](../services/web/server/src/simcore_service_webserver/projects/_projects_service.py#L763)).
- As a platform I take that EC2 and subtract some pre-defined resources for the
  system + OPS services
  ([`estimate_dynamic_sidecar_resources_from_ec2_instance()`](../packages/service-library/src/servicelib/docker_utils.py#L454)).
- As a platform I define some minimal resources for the sidecars, subtracted
  upfront via RPC
  ([`compute_helper_containers_resources()`](../services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/docker_service_specs/resources.py),
  exposed in [`api/rpc/_resources.py`](../services/director-v2/src/simcore_service_director_v2/api/rpc/_resources.py)).
- As a platform I can directly check that the chosen pricing plan is usable or
  not and raise an error in case it is not: `InsufficientResourcesForHelperContainersError`,
  HTTP 422
  ([`_rest_exceptions.py`](../services/web/server/src/simcore_service_webserver/projects/_controller/_rest_exceptions.py)).
- As a platform I then start the services with the defined resources, and then
  scale up accordingly and it shall never fail at that point: the same helper
  overhead gets re-added when actually scheduling
  ([`_add_helper_containers_resources_to_service_resources()`](../services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/scheduler/_core/_event_create_sidecars.py#L97)),
  so the final ask matches what was already validated to fit.

### Non-Billable

- As a user I have a service made of 1 or X containers that have some
  reservations/limits defined: same catalog-declared resources as above, used
  as-is — `update_project_node_resources_from_hardware_info()` is never called
  on this path.
- As a platform I define some minimal resources for the sidecars: the exact
  same [`compute_helper_containers_resources()`](../services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/docker_service_specs/resources.py)
  as the billable path — no separate definition, no scaling factor.
- As a platform I then start the services with the defined resources: same
  [`_add_helper_containers_resources_to_service_resources()`](../services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/scheduler/_core/_event_create_sidecars.py#L97)
  call site as above.
- As a platform I then scale up accordingly and try to find an EC2 that can
  cope. It will fail at that point if there are no EC2 able to fit: correct —
  there is no pre-check equivalent to the billable path's error here.
