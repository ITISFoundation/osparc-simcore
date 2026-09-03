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

A dynamic service is made of 1 to N docker containers with resources
reservations/limits defined (e.g. RAM, #CPUs, #GPUs, VRAM, ...). Depending on
whether the product is billable or non-billable, one of the two flows below
applies per project/node.

### Billable

- As a user I have a service made of 1 or X containers that have some
  resources reservations/limits defined (e.g. RAM, #CPUs, #GPUs, VRAM, ...).
- As a user I define a pricing plan, which defines an AWS EC2 instance type
  (e.g. a specific computer instance).
- As a user I start the service with my selected pricing plan.
- As a platform I ask director-v2 to fit the node onto that machine, since it
  owns the resource model of a dynamic service. In one call it:
  - subtracts pre-defined resources for the system + OPS services,
  - subtracts what the dynamic-sidecar itself and its helper containers need,
  - returns the resources to store for the user service.
- As a platform I can directly check that the chosen pricing plan is usable or
  not and raise an error in case it is not: `InsufficientInstanceResourcesError`.
- As a platform I then start the services with the defined resources, and then
  scale up accordingly and it shall never fail at that point: the same
  sidecar + helper overhead gets re-added when actually scheduling, so the
  final ask matches what was already validated to fit.

### Non-Billable

- As a user I have a service made of 1 or X containers that have some
  resources reservations/limits defined (e.g. RAM, #CPUs, #GPUs, VRAM, ...),
  used as-is: no pricing plan is involved on this path.
- As a user I can change the service required resources as I wish.
- As a platform I define some minimal resources for the sidecar and its helper
  containers, the same as the billable path — no separate definition, no
  scaling factor.
- As a platform I then start the services with the defined resources.
- As a platform I then scale up accordingly and try to find an EC2 that can
  cope. It will fail at that point if there are no EC2 able to fit: correct —
  there is no pre-check equivalent to the billable path's error here.
