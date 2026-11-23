# Test Suites and Their Infrastructure

Inventory of every job in
[`ci-build-test.yml`](../../.github/workflows/ci-build-test.yml) and what it
needs to run. It feeds
[`ci-build-test-k8s.yml`](../../.github/workflows/ci-build-test-k8s.yml):
only the rows with `none` infra run without a cluster.

## What makes a test need Docker

`pytest_simcore` fixtures that take their endpoints from a deployed stack
need a Docker daemon and `docker stack deploy`: `postgres_dsn` (and through
it `postgres_engine`, `postgres_db`, `sqlalchemy_async_engine`,
`asyncpg_engine`), `redis_settings`/`redis_service`,
`rabbit_env_vars_dict`/`rabbit_service`,
`docker_api`/`docker_client`/`async_docker_client`, `docker_registry`, and
everything in `pytest_simcore.docker_compose`/`docker_swarm`. Declaring those
plugins in `conftest.py` is not enough — a test, or a fixture it uses, has to
request one. Suites may also need host binaries: `rclone`
(`ci/github/helpers/install_rclone.bash`) and 7zip (`install_7zip.bash`).

The `<n>/<total>` count below is the number of test files naming a
Docker-backed fixture. Run this from the repository root, per test path, and
treat it as a first filter rather than a verdict:

```bash
pat='postgres_db|postgres_engine|postgres_dsn|postgres_live_stack'
pat+='|postgres_env_vars|sqlalchemy_async_engine|asyncpg_engine'
pat+='|docker_swarm|docker_api|docker_client|async_docker_client'
pat+='|rabbit_service|rabbit_settings|rabbitserver'
pat+='|redis_service|redis_settings|redisserver'
pat+='|docker_registry|registry_settings|docker_network'
pat+='|docker_compose_file|swarm_cluster|osparc_service'
pat+='|webserver_service|storage_service|dask_scheduler_service|httpbin'
grep -rlEw "$pat" <test path> --include='test_*.py'
```

Four matches are names rather than fixtures, so those files run without a
daemon: `models-library` and `webserver isolated` (an `httpbin.org` URL in a
fixture value), `settings-library` (the `settings_library.docker_registry`
import), `api-server` (a local variable). Three suites reach a Docker fixture
only through `conftest.py`: `agent`
(`unit/conftest.py: service_env <- rabbit_service`), `notifications`
(`unit/conftest.py: app_environment <- rabbit_service, redis_service,
postgres_db`, used by `test_cli.py`), and the five files under `api-server`'s
`tests/unit/_with_db/`.

## Unit tests

Every suite runs through `ci/github/unit-testing/<suite>.bash` except
`clusters-keeper` and `resource-usage-tracker`, which call `make` inline in
the workflow. Each line reads: suite, infra it needs, docker files, whether
`ci-build-test-k8s.yml` has a job for it (`k8s`), then the test path.
`docker` means a Docker daemon.

- `agent`: rabbit (conftest), rclone (0/9, k8s: no)
  `services/agent/tests/unit`
- `api`: none (0/5, k8s: yes)
  `api/tests`
- `api-server`: postgres in `_with_db` (1/70, k8s: no)
  `services/api-server/tests/unit`
- `autoscaling`: docker (6/26, k8s: no)
  `services/autoscaling/tests/unit`
- `aws-library`: none (0/13, k8s: yes)
  `packages/aws-library/tests`
- `catalog`: postgres, rabbit (5/25, k8s: no)
  `services/catalog/tests/unit`
- `celery-library`: none, memory broker and in-memory redis (0/9, k8s: yes)
  `packages/celery-library/tests`
- `clusters-keeper`: docker (4/21, k8s: no)
  `services/clusters-keeper/tests/unit`
- `common-library`: none (0/19, k8s: yes)
  `packages/common-library/tests`
- `dask-sidecar`: docker, rabbit (1/19, k8s: no)
  `services/dask-sidecar/tests/unit`
- `dask-task-models-library`: none (0/10, k8s: yes)
  `packages/dask-task-models-library/tests`
- `datcore-adapter`: none (0/8, k8s: yes)
  `services/datcore-adapter/tests/unit`
- `director`: docker, registry (4/11, k8s: no)
  `services/director/tests/unit`
- `director-v2`: postgres, redis, rabbit, docker (20/66, k8s: no)
  `services/director-v2/tests/unit`
- `dynamic-scheduler`: postgres, redis, rabbit (7/20, k8s: no)
  `services/dynamic-scheduler/tests/unit`
- `dynamic-sidecar`: docker, redis, rclone, 7zip (10/46, k8s: no)
  `services/dynamic-sidecar/tests/unit`
- `invitations`: none (0/9, k8s: yes)
  `services/invitations/tests/unit`
- `models-library`: none (1/65, k8s: yes)
  `packages/models-library/tests`
- `notifications`: postgres, rabbit, redis (all via conftest) (0/13, k8s: no)
  `services/notifications/tests/unit`
- `payments`: postgres, rabbit (8/25, k8s: no)
  `services/payments/tests/unit`
- `postgres-database`: postgres (23/34, k8s: no)
  `packages/postgres-database/tests`
- `pytest-simcore`: docker, its own fixtures (3/16, k8s: no)
  `packages/pytest-simcore/tests`
- `python-linting`: none (k8s: yes)
  repo-wide `make pylint`, no test files
- `resource-usage-tracker`: postgres, rabbit, redis (17/25, k8s: no)
  `services/resource-usage-tracker/tests/unit`
- `service-integration`: none (0/18, k8s: yes)
  `packages/service-integration/tests`
- `service-library`: docker, registry, postgres, rabbit (23/93, k8s: no)
  `packages/service-library/tests`
- `settings-library`: none (1/17, k8s: yes)
  `packages/settings-library/tests`
- `simcore-sdk`: rclone container (1/18, k8s: no)
  `packages/simcore-sdk/tests/unit`
- `static-webserver`: none (k8s: yes)
  `services/static-webserver/client/tests`, run with `node --test`
- `storage 01/02`: postgres, s3, rclone (8/26, k8s: no)
  `services/storage/tests/unit`
- `webserver isolated`: none (1/70, k8s: yes)
  `services/web/server/tests/unit/isolated`
- `webserver with_dbs 01-04`: postgres, redis, rabbit (64/163, k8s: no)
  `services/web/server/tests/unit/with_dbs`

`migration` has a change filter but no test job.

## Integration and system tests

All of them load images produced by `build-test-images` into a Docker daemon,
so none runs in the K8s workflow yet. Scripts live in
`ci/github/integration-testing/` and `ci/github/system-testing/`.

- `[int] director-v2 01/02`: images, swarm stacks, dask, postgres, rclone
  (job 02). `director-v2.bash`
- `[int] docker-api-proxy`: images, swarm stacks. `docker-api-proxy.bash`
- `[int] dynamic-sidecar`: images, swarm stacks, rclone. `dynamic-sidecar.bash`
- `[int] simcore-sdk`: images, postgres, s3, rclone. `simcore-sdk.bash`
- `[int] webserver 01`: images, swarm stacks. `webserver.bash`
- `[sys] e2e-playwright`: full stack deployed with `docker stack deploy`.
  `e2e-playwright.bash`
- `[sys] environment-setup`: none; the compose check skips itself when
  `SIMCORE_CLUSTER_ORCHESTRATOR=k8s`. `environment-setup.bash`
- `[sys] public-api`: full stack deployed with `docker stack deploy`.
  `public-api.bash`

`unit-tests`, `integration-tests` and `system-tests` are aggregation jobs and
GitHub required checks. `deploy` publishes images on `master` and hotfix
pushes only.

## Gaps

- `payments` needs a split or a postgres job before it joins the no-infra
  jobs: these 8 of 25 unit test files request `postgres_db` or
  `sqlalchemy_async_engine`, which resolve to `docker_stack`:
  `test_db_payments_methods_repo.py`, `test_db_payments_transactions_repo.py`,
  `test_rpc_payments.py`, `test_rpc_payments_methods.py`,
  `test_services_auto_recharge_listener.py`,
  `test_services_payments__get_invoice.py`,
  `api/test__one_time_payment_workflows.py`,
  `api/test__payment_method_workflows.py`.
- Suites that need Docker in a few files only cannot join the no-infra jobs
  without a split: `api-server` (`_with_db`, 5 files), `simcore-sdk`
  (`test_node_ports_common_r_clone_mount.py`), `dask-sidecar`
  (`test_computational_docker_utils.py`), `pytest-simcore` (3 files),
  `service-library` (23 of 93).
