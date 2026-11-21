# CI Build & Test on Kubernetes — Important Decisions

Add a Kubernetes flavor to `ci-build-test.yml`. No backend changes; Swarm-based services may fail.

## ❓ Open questions

### Flavor wiring

How is the Kubernetes flavor passed through each layer?

**GitHub Actions:** 
What does a k8s-flavor job look like (e.g. e2e)? Matrix axis or separate job?

**Flavor selection:**
How is the flavor set? (env var, e.g. `SIMCORE_FLAVOR=k8s|swarm`, make variable, pytest option?)

**Makefile:**
Which targets change? Does the root `Makefile` delegate to `k8s/Makefile`?

**pytest:**
How do fixtures pick the flavor? How are Swarm-logic tests marked (e.g. `@pytest.mark.swarm_only`)?

### Debug artifacts

`kubectl` logs/events on failure?

---

## ✅ Decided

### Rollout strategy

Step by step, starting with the simplest unit tests:

1. Unit test without infra — validates the GitHub Actions flow only
2. Unit test with postgres only (`packages/postgres-database`) — first real k8s test
3. Unit tests with more infra (e.g. `web/server/tests/unit/with_dbs`)
4. Integration tests, then system tests

### Scope

All tests. ⚠️ Some unit tests use Swarm as test infra (e.g. `web/server/tests/unit/with_dbs`) — keep Swarm on the runner for them.

### Expected failures

Everything must be green, except tests of Swarm-based logic.

### Cluster & deploy

Reuse `k8s/Makefile` only (`create-cluster`, `load-images-into-cluster`, `helmfile-apply`, `delete-cluster`). No custom kubectl/kind/helm steps in CI.

### Triggers

Same as `ci-build-test.yml` (push, pull_request, merge_group, workflow_dispatch).
