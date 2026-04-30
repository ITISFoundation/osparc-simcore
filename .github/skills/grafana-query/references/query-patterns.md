# Common Query Patterns

All queries below use `<LOKI_UID>` and `<PROM_UID>` as placeholders. Resolve these first via `mcp_grafana_list_datasources`.

The service name prefix `<PREFIX>` (e.g., `simcore_staging`, `simcore_production`) varies by deployment. Discover it via `mcp_grafana_list_loki_label_values(labelName="service_name")` and look for the pattern used by core services like `*_webserver`.

## LogQL (Loki)

### Error Logs from All Simcore Services

```logql
{service_name=~"<PREFIX>_.*"} |~ "(?i)error|exception|traceback|critical"
```

> **Note**: The broad regex filter is needed because non-Python services (traefik, redis) don't use structured `log_level`. Exclude noise with additional filters:
> ```logql
> {service_name=~"<PREFIX>_.*"} |~ "(?i)error|exception|traceback|critical" != "Health check failed" != "/metrics"
> ```

### Errors from a Specific Service

```logql
{service_name="<PREFIX>_webserver"} | json | log_level = `ERROR`
```

Replace `webserver` with: `api-server`, `director-v2`, `catalog`, `dynamic-schdlr`, `agent`, `autoscaling`, `wb-garbage-collector`, etc.

### Warnings and Errors (Excluding INFO)

```logql
{service_name=~"<PREFIX>_.*"} | json | log_level != `INFO`
```

### Logs for a Specific User

```logql
{service_name=~"<PREFIX>_.*"} | json | log_uid = `<user-id>`
```

### Logs with a Specific Trace ID

```logql
{service_name=~"<PREFIX>_.*"} | json | log_trace_id = `<trace-id>`
```

### Error Count per Service (Last Hour)

```logql
count_over_time({service_name=~"<PREFIX>_.*"} |~ "(?i)error|exception|traceback|critical" [1h])
```
Use with `queryType: "instant"` to get totals.

### Rate of Errors (for alerting/dashboards)

```logql
sum by (service_name) (rate({service_name=~"<PREFIX>_.*"} |~ "(?i)error" [5m]))
```

### Dynamic Service Logs (dy-proxy / dy-sidecar)

```logql
{service_name=~"dy-proxy_<node-uuid>"}
{service_name=~"dy-sidecar_<node-uuid>"}
```

### Traefik Errors (Connection Refused, 5xx, etc.)

```logql
{service_name=~".*_traefik"} |~ "(?i)error|ERR" != "Health check failed"
```

> The fallback health check warnings (`connection refused` on port `:0`) are **expected** and can be excluded. These are intentional fallback backends that return 503 when the primary is down.

## PromQL (Prometheus)

### HTTP Request Rate by Service

```promql
sum by (service_name) (rate(http_requests_total[5m]))
```

### HTTP Error Rate (5xx)

```promql
sum by (service_name) (rate(http_requests_total{status=~"5.."}[5m]))
```

### Request Latency (p95)

```promql
histogram_quantile(0.95, sum by (le, service_name) (rate(http_request_duration_seconds_bucket[5m])))
```

### Container Memory Usage

```promql
container_memory_usage_bytes{container_label_com_docker_swarm_service_name=~"<PREFIX>_.*"}
```

### Container CPU Usage

```promql
rate(container_cpu_usage_seconds_total{container_label_com_docker_swarm_service_name=~"<PREFIX>_.*"}[5m])
```

## Workflow: Investigating an Error

1. **Start broad** — query errors across all services:
   ```logql
   {service_name=~"<PREFIX>_.*"} |~ "(?i)error|exception|traceback|critical" != "Health check failed"
   ```

2. **Narrow down** — filter to the specific service:
   ```logql
   {service_name="<PREFIX>_<service>"} | json | log_level = `ERROR`
   ```

3. **Get context** — look at surrounding logs (use `direction: "forward"` and a narrow time window around the error timestamp)

4. **Check traces** — if `log_trace_id` is not `"0"`, query Tempo for the full distributed trace

5. **Check metrics** — look at the service's request rate and error rate around the same time to understand impact

## Tips

- Default time range is **last 1 hour** if not specified
- Use `limit` parameter to control result count (max 100 for Loki queries via MCP)
- Use `direction: "backward"` (default) for newest-first, `"forward"` for oldest-first
- Use `queryType: "instant"` for metric queries that return a single value
- The `stepSeconds` parameter controls resolution for range metric queries
- Always check `query_loki_stats` first if unsure whether a selector matches any streams
