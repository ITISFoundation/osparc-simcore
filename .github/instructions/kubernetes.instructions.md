---
applyTo: 'k8s/**,services/helmfile*,services/**/helm-values*.yaml.gotmpl'
---

# Kubernetes instructions

## Layout

- OPS services (postgres, s3, ...) live in `services/helmfile.local-ops.yaml.gotmpl`;
  simcore services live in `services/helmfile.yaml.gotmpl`.
  - Traefik is exception and lives with simcore services
- Every simcore release inherits the `simcore-service` template
- Pin `version:` for every upstream (non-local) chart.

## Release Values files

- `_shared/helm-values.<dependency>.yaml.gotmpl`: env reused by multiple releases
  (postgres, rabbit, catalog, ...).
- `<service>/helm-values.yaml.gotmpl`: base of the service: image, resources,
  env, probes.
- `<service>/helm-values.<flavor>.yaml.gotmpl`: one flavor of the same image
  (e.g. `sto-worker`, `api-worker`). Only the differences to the base.
- `<service>/helm-values.local[.<flavor>].yaml.gotmpl`: environment specific
  override (e.g., for local image, debug port, source mounts. Registered in
  `services/helmfile-environments.local.yaml`)

## Environment variables

- Rely on environment variables defined in `.env-devel`.
- New variables go in `.env-devel`; kubernetes-cluster-specific overrides (DNS names
  `<svc>.ops.svc.cluster.local`) go in `k8s/.env-devel-k8s-override`.
- Passwords, keys and tokens go under `secretEnv`, everything else under `env`.
  Keep both maps sorted alphabetically.

## Helmfile Releases

- Define explicitly resource requests and limits for every release.
- Keep the chart's security as strict as possible. Every relaxation
  (`readOnlyRootFilesystem: false`, root user, capabilities) needs a comment with
  the reason.
- Exposing services: use Traefik Ingress

## Validation

- `make -C k8s helmfile-lint` and `make -C k8s helmfile-template` must pass.
