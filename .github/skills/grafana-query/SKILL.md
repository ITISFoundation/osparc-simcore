---
name: grafana-query
description: "Query Grafana for logs, metrics, traces, and alerts from an osparc-simcore deployment. Use when: debugging service errors, querying service logs, querying Prometheus metrics, investigating incidents, finding error patterns, viewing dashboards, checking alert rules, or analyzing service performance."
argument-hint: "Describe what you want to investigate (e.g., 'errors in webserver last hour', 'memory usage of director-v2')"
---

# Grafana Query

Every osparc deployment exposes monitoring the same way: a Grafana instance in
front of the Victoria stack (VictoriaLogs, VictoriaMetrics, VictoriaTraces). Only
the datasource UIDs, the service name prefix and the dashboard set vary, so this
skill states the common shape and marks what to discover per deployment.

## When to Use

- Investigating errors or warnings in simcore services
- Checking service logs for specific events or patterns
- Querying metrics (request rates, latencies, resource usage)
- Viewing distributed traces
- Checking alert rule state
- Analyzing service performance or resource consumption

> **IMPORTANT**: If you discover that the actual Grafana data (datasource types,
> label names, log field structures, dashboard names, service naming patterns) is
> inconsistent with what this skill documents, **update the skill files** to
> reflect the correct state. This keeps the skill accurate for later use.

## Access

Read access uses a service account token, passed to the Grafana MCP server as
`GRAFANA_URL` and `GRAFANA_SERVICE_ACCOUNT_TOKEN` (see
`.vscode/mcp.template.json`). Point the server at another deployment's URL and
token to query that deployment.

The Grafana base URL is not stored in this repository. Any MCP tool response that
returns a link (`exploreUrl` or `url` field) contains it. Only `<base>/api/health`
answers without a token; it reports the Grafana version, which is not pinned
across deployments. Every other endpoint returns 401.

## Naming placeholder

`<stack>` is the deployment's Swarm stack name, `SWARM_STACK_NAME`. It looks like
`<prefix>-simcore_<env>`: `master-simcore_master`, `staging-simcore_staging`,
`production-simcore_production`. `scripts/release/monitor_release/settings.py`
lists the known values. Discover the one in front of you by listing log
`service_name` values with a `matcher` and reading the prefix shared by
`*_webserver`.

## Datasources

Datasource UIDs differ per deployment. **Always discover them dynamically** at the
start of a query session by listing datasources, filtering by type if needed.
Their names are the same across deployments:

| UID | Type | Purpose |
| --- | --- | --- |
| `victoria-logs` | victoriametrics-logs-datasource | all service logs |
| `victoria-metrics` | prometheus | default datasource, all targets |
| `victoria-metrics-swarm` | prometheus | Docker Swarm targets only |
| `victoria-metrics-kubernetes` | prometheus | Kubernetes targets only |
| `victoria-traces` | tempo | distributed tracing |

The log tools take LogsQL on a VictoriaLogs datasource, not LogQL. LogsQL has no
`| json` pipe, so a LogQL query such as

```logql
{service_name=~"<stack>_.*"} | json | log_level = `ERROR`
```

fails with `unexpected pipe name "json"`. Use field filters instead, see
[Query Patterns](./references/query-patterns.md).

## Dashboards

Dashboard UIDs differ per deployment. **Always discover them dynamically**:
searching without a query lists all of them. The folder layout is shared.

Simcore folder:

| Title | Purpose |
| --- | --- |
| Services | resources, HTTP and RPC handling per service |
| Requests load overview | HTTP request load across services |

Open `Services` once an error is traced to one simcore service.

OPS Apps folder: RabbitMQ Overview, Redis Overview, Postgres Overview, Docker
Registries, Traefik Internal State, OpenTelemetry Collector, Grafana Internal
Metrics, plus the self-monitoring dashboards for VictoriaMetrics (federated,
vmalert, cluster), VictoriaLogs and VictoriaTraces.

System folder: Swarm Nodes (node-exporter), Kubernetes Nodes, GPU Nodes (DCGM).

Vendor folder: dashboards a single deployment adds.

## Procedure

### 0. Discover Datasources

Before any query, resolve the datasource UIDs and the `<stack>` prefix of this
deployment.

### 1. Identify the Target

Determine which service or services to investigate. Naming differs between logs
and metrics:

- logs: `service_name` holds the full Swarm name, `<stack>_<service>`
- metrics: `service_name` holds the bare name, `webserver`
- container metrics: the full name is in
  `container_label_com_docker_swarm_service_name`

The service part is the compose service name, so `services/docker-compose.yml`
lists what a deployment can run: `webserver`, `static-webserver`, `api-server`,
`api-worker`, `catalog`, `director`, `director-v2`, `dynamic-schdlr`, `agent`,
`dask-scheduler`, `dask-sidecar`, `storage`, `sto-worker`,
`sto-worker-cpu-bound`, `resource-usage-tracker`, `wb-api-server`, `wb-auth`,
`wb-db-event-listener`, `wb-garbage-collector`, `notifications`,
`notifications-worker`, `payments`, `invitations`, `datcore-adapter`,
`autoscaling`, `clusters-keeper`, `migration`, `traefik`, `postgres`, `redis`.
A deployment runs a subset, so confirm the name in the logs before querying it.

Dynamic services have their own streams: `dy-proxy_<node-uuid>`,
`dy-sidecar_<node-uuid>`, and one container per user service (`<service>_<uuid>`,
`jsonifier_<uuid>`, `sleeper_<uuid>`). On a busy deployment these dominate the
`service_name` values.

### 2. Query Logs

Use the logs datasource UID from step 0. Labels:

- `service_name`: service identifier, see the naming patterns above
- `container_name`: container name with replica and task ID
- `host`: Swarm node hostname
- `source_type`: log pipeline source, `docker_swarm_logs` for Swarm workloads
- `log_level`, `log_source`, `log_uid`, `log_oec`, `log_trace_id`, `log_span_id`:
  structured fields of the simcore Python logger
- `kubernetes.*`: Kubernetes stacks (monitoring, logging)

`list_loki_label_values` has no `limit` argument. Called without a `matcher` it
returned 57303 `service_name` values, 2.2 MB, on a busy deployment, because of
the dynamic-service streams. Pass `matcher`, for example
`{source_type="docker_swarm_logs"}`.

See [Log Structure](./references/log-structure.md) for the field details.

### 3. Query Metrics

Use the default metrics datasource UID from step 0. Metric families:

- `http_requests_total`: labels `service_name`, `http_status`, `method`,
  `simcore_user_agent`
- `http_request_latency_seconds_with_labels_bucket`, `_sum`, `_count`: request
  latency histogram
- `http_in_flight_requests`, `asyncio_event_loop_*`, `process_*`, `python_gc_*`
- `container_memory_working_set_bytes`, `container_cpu_usage_seconds_total`:
  container metrics, selected by
  `container_label_com_docker_swarm_service_name`
- business metrics per service, for example
  `simcore_simcore_service_webserver_services_started_total`

Discover a service's own families by listing metric names with a regex, for
example `simcore_simcore_service_webserver.*`.

### 4. Query Traces

Use the traces datasource UID from step 0. Traces carry the OpenTelemetry service
names (`simcore-service-catalog`, `simcore-service-director`,
`simcore-service-dynamic-scheduler`), not the log `service_name`. A span name is
the traced function. Fetch a trace by ID instead of searching for it: the
`log_trace_id` field of a simcore log line holds that ID.

## Common Query Patterns

See [Query Patterns](./references/query-patterns.md) for LogsQL and PromQL
queries.

Last updated: 2026-11-18. Verified on a master deployment; the datasource UIDs,
label names and metric families are the shared monitoring setup, and the service
name prefix is what changes per deployment.
