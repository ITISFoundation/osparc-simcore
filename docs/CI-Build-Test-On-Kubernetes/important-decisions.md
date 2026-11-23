# CI Build & Test on Kubernetes — Important Decisions

Add a Kubernetes flavor to the CI Build Tests (`ci-build-test.yml`).
No backend changes; Swarm-based services may fail.

## ❓ Open questions

### Flavor wiring

How is the Kubernetes flavor passed through each layer?

**Flavor selection:**
How is the flavor set? (env var, e.g. `SIMCORE_FLAVOR=k8s|swarm`, make
variable, pytest option?)

**Makefile:**
Which targets change? Does the root `Makefile` delegate to `k8s/Makefile`?

### Debug artifacts

`kubectl` logs/events on failure?

---

## ✅ Decided

### Workflow

Own workflow file (e.g. `.github/workflows/ci-build-test-k8s.yml`).
`ci-build-test.yml` stays untouched.

### Interfaces

Minimal changes to existing interfaces (Makefiles, test invocation, CI
scripts, ...). New ones shall resemble existing ones

### pytest flavor selection

pytest option `--simcore-cluster-orchestrator=k8s|docker_swarm` in the
`simcore` option group of `pytest-simcore`, like `--keep-docker-up`. The
default comes from `SIMCORE_CLUSTER_ORCHESTRATOR`, else `docker_swarm`.

### Rollout strategy

Step by step, starting with the simplest unit tests:

1. Unit test without infra — validates the GitHub Actions flow only
2. Unit test with postgres only (`packages/postgres-database`) — first real
   k8s test
3. Unit tests with more infra (e.g. `web/server/tests/unit/with_dbs`)
4. Integration tests, then system tests

### Scope

All tests.

### Expected failures

Everything must be green, except tests of Swarm-based logic.

### Swarm-only (non-backend) tests

Do not touch them.

### Cluster & deploy

Reuse `k8s/Makefile` only. No custom kubectl/kind/helm calls.

### Infra lifecycle

pytest fixtures create and remove the cluster and its releases, as for
Swarm.

### Triggers

Only on changes in k8s files (`pull_request` with `paths`, like
`ci-k8s-charts.yml`) + `workflow_dispatch`.
