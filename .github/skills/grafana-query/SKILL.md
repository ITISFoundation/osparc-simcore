---
name: grafana-query
description: "Query Grafana for logs, metrics, traces, and alerts from an osparc-simcore deployment. Use when: debugging service errors, checking logs in Loki, querying Prometheus metrics, investigating incidents, finding error patterns, viewing dashboards, checking alert rules, or analyzing service performance."
argument-hint: "Describe what you want to investigate (e.g., 'errors in webserver last hour', 'memory usage of director-v2')"
---

# Grafana Query

## When to Use

- Investigating errors or warnings in simcore services
- Checking service logs for specific events or patterns
- Querying Prometheus metrics (request rates, latencies, resource usage)
- Viewing distributed traces via Tempo
- Checking alert rule state
- Analyzing service performance or resource consumption

## Datasources

Datasource UIDs differ per deployment. **Always discover them dynamically** at the start of a query session:

1. Use `mcp_grafana_list_datasources` to list all datasources and their UIDs
2. Filter by type when needed: `type: "loki"`, `type: "prometheus"`, `type: "tempo"`

Expected datasource types in a typical deployment:

| Name pattern | Type | Purpose |
|--------------|------|---------|
| loki | Loki | Log aggregation (all service logs) |
| prometheus-federation | Prometheus | Federated metrics (usually the default datasource) |
| prometheus-catchall | Prometheus | Catchall Prometheus metrics |
| tempo | Tempo | Distributed tracing |
| cloudwatch | CloudWatch | AWS infrastructure metrics (RDS, etc.) |

## Dashboards

Dashboard UIDs differ per deployment. **Always discover them dynamically**:

1. Use `mcp_grafana_search_dashboards` to find dashboards by name
2. Use `mcp_grafana_get_dashboard_summary` with the UID to inspect a specific dashboard

Typical dashboard folders and their contents:

### simcore folder
| Title | Purpose |
|-------|---------|
| Metrics | Core simcore service metrics |
| Services | Service-level overview |
| Requests load overview | HTTP request load |
| autoscaling overview | Autoscaling status |
| API server log streaming queues | API server queues |
| s4l-lite admin overview | Sim4Life Lite admin |

### ops folder
| Title | Purpose |
|-------|---------|
| Traefik2 | Reverse proxy metrics |
| RabbitMQ Overview | Message broker |
| Redis Overview | Cache/queue |
| Postgres Overview | Database metrics |
| Docker Registries | Registry health |
| AWS RDS Metrics | RDS database |

### system folder
| Title | Purpose |
|-------|---------|
| Docker Swarm Overview | Cluster overview |
| Nodes - Overview | Host nodes |
| Nodes - Detailed Insights | Per-node deep dive |

## Procedure

### 0. Discover Datasources

Before any query, resolve the datasource UIDs for this deployment:
```
mcp_grafana_list_datasources → note the UIDs for loki, prometheus, tempo
```

### 1. Identify the Target

Determine which service(s) to investigate. The simcore platform services use the naming pattern `<stack>_<prefix>_<service>` (e.g., `simcore_staging_webserver`). The exact stack/prefix varies by deployment.

**Discover the naming pattern** by listing Loki label values:
```
mcp_grafana_list_loki_label_values(datasourceUid=<loki-uid>, labelName="service_name")
```

Common service name patterns:
- **Core services**: `<stack>_<prefix>_<service>` (e.g., `*_webserver`, `*_api-server`, `*_director-v2`)
- **Dynamic proxies**: `dy-proxy_<node-uuid>`
- **Dynamic sidecars**: `dy-sidecar_<node-uuid>`
- **Dask**: `dask_stack_<component>`

Core simcore services:
`webserver`, `api-server`, `director`, `director-v2`, `catalog`, `dynamic-schdlr`, `agent`, `autoscaling`, `clusters-keeper`, `resource-usage-tracker`, `wb-api-server`, `wb-auth`, `wb-db-event-listener`, `wb-garbage-collector`, `payments`, `invitations`, `efs-guardian`, `datcore-adapter`, `traefik`

### 2. Query Logs (Loki)

Use the Loki datasource UID discovered in step 0. Available Loki labels:
- `service_name` — service identifier (see naming patterns above)
- `container_name` — Docker container name with replica info
- `host` — host node name
- `source` — log pipeline source (typically `vector`)

See [Log Structure Reference](./references/log-structure.md) for JSON field details.

### 3. Query Metrics (Prometheus)

Use the Prometheus datasource UID discovered in step 0 (prefer the federation/default one). Common metric patterns:
- HTTP request metrics from gunicorn/aiohttp
- Service-specific business metrics
- Docker/container resource metrics

### 4. Query Traces (Tempo)

Use the Tempo datasource UID discovered in step 0. Traces are correlated with logs via `log_trace_id` and `log_span_id` fields in log entries.

### 5. Check Alerts

Use `mcp_grafana_alerting_manage_rules` with `operation: "list"` to view configured alert rules and their current states.

## Common Query Patterns

See [Query Patterns Reference](./references/query-patterns.md) for ready-to-use LogQL and PromQL queries.
