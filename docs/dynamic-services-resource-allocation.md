# Dynamic services: CPU/RAM resource allocation

Answers: *"how do we define CPU/RAM resources for a dynamic service and its helper
containers, for both billable and non-billable products?"* (raised in review by
@sanderegg on PR `pr-osparc-properly-allocate-extra-container-resources`).

Written as user stories, mirroring how the question was originally asked. Only
one of the two flows below runs per project/node, depending on whether the
product charges credits for compute
([`_projects_service.py`](../services/web/server/src/simcore_service_webserver/projects/_projects_service.py),
"Get wallet/pricing/hardware information" block).

## 1. Billable

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
  ([`compute_helper_containers_resources()`](../services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/docker_service_specs/settings.py#L76),
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

## 2. Non-Billable

- As a user I have a service made of 1 or X containers that have some
  reservations/limits defined: same catalog-declared resources as above, used
  as-is — `update_project_node_resources_from_hardware_info()` is never called
  on this path.
- As a platform I define some minimal resources for the sidecars: the exact
  same [`compute_helper_containers_resources()`](../services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/docker_service_specs/settings.py#L76)
  as the billable path — no separate definition, no scaling factor.
- As a platform I then start the services with the defined resources: same
  [`_add_helper_containers_resources_to_service_resources()`](../services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/scheduler/_core/_event_create_sidecars.py#L97)
  call site as above.
- As a platform I then scale up accordingly and try to find an EC2 that can
  cope. It will fail at that point if there are no EC2 able to fit: correct —
  there is no pre-check equivalent to the billable path's error here.

## Known gap

The "raise an error if the plan can't fit" step only exists for the **billable**
path. Flagged here for a possible follow-up, not addressed by this PR.
