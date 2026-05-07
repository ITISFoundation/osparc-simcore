# Common Query Patterns

All queries below use `<LOKI_UID>` and `<PROM_UID>` as placeholders. Resolve these first by listing the available datasources.

The service name prefix `<PREFIX>` (e.g., `simcore_staging`, `simcore_production`) varies by deployment. Discover it by listing the Loki label values and look for the pattern used by core services like `*_webserver`.

## LogQL (Loki)

### Logs by specific log level from all Simcore Services

```logql
{service_name=~".*simcore.*"} | json | log_level = `ERROR`
```
Replace `ERROR` by `WARNING`, `INFO`, `DEBUG` to change the log level.

### To get error logs from a specific simcore service

```logql
{service_name="<PREFIX>_webserver"} | json | log_level = `ERROR`
```

Replace `webserver` with: `api-server`, `director-v2`, `catalog`, `dynamic-schdlr`, `agent`, `autoscaling`, `wb-garbage-collector`, etc.


### Logs from Simcore services with a Specific Trace ID

```logql
{service_name=~".*simcore.*"} | json | log_trace_id = `<trace-id>`
```

### Dynamic Service Logs (dy-proxy / dy-sidecar)

```logql
{service_name=~"dy-proxy_<node-uuid>"}
{service_name=~"dy-sidecar_<node-uuid>"}
```

### Error logs from any services (not only Simcore services)

Non-simcore services have a different logging format. Hence, in this case it is easiest to check if for loglines containing a regex

```logql
{source="vector"} |~ "(?i)error|ERR"
```

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

1. **Start by checking for errors in simcore services** — query errors across all simcore services:
   ```logql
   {service_name=".*simcore.*"} | json | log_level = `ERROR`
   ```
   Only if this doesn't return any results, search more broadly for errors among all services
   ```logql
   {source="vector"} |~ "(?i)error|ERR"
   ```

2. **Narrow down**
   If an error log is found and the log is emitted while handling a request, a simcore service log will have a `log_trace_id` field.
   narrow down by investigating all simcore service logs from that trace
   ```logql
   {service_name=".*simcore.*"} | json | log_trace_id=<trace id>
   ```

  If the error log does not have a trace id it is typically because it was not emitted while handling a request. In that case filter to the specific service:
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
