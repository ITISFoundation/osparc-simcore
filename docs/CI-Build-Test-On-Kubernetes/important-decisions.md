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

**pytest:**
How do fixtures pick the flavor? How are Swarm-logic tests marked (e.g.
`@pytest.mark.swarm_only`)?

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

Tests of pure Swarm artifacts (e.g. compose files), not backend logic, are
skipped: `SIMCORE_CLUSTER_ORCHESTRATOR=k8s` (set in the workflow) +
`@pytest.mark.skipif` on the test.

### Cluster & deploy

Reuse `k8s/Makefile` only (`create-cluster`, `load-images-into-cluster`,
`helmfile-apply`, `delete-cluster`). No custom kubectl/kind/helm steps in CI.

### Infra lifecycle

The cluster and its releases are created outside pytest: by the workflow in
CI, by the developer locally, both via `k8s/Makefile`. In k8s mode, pytest
never calls `create-cluster`, `helmfile-apply` or similar; it only connects to
the deployed services.

### Triggers

Only on changes in k8s files (`pull_request` with `paths`, like
`ci-k8s-charts.yml`) + `workflow_dispatch`.
