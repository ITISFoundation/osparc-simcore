# Common Query Patterns

The queries below use the master datasource UIDs (`victoria-logs`,
`victoria-metrics`, `victoria-traces`) and master service names:
`master-simcore_master_<service>` in logs, bare `<service>` in metrics. On another
deployment, resolve both first. List the datasources, then list log label values
with a `matcher` and look for the pattern used by `*_webserver`.

## Logs (LogsQL)

LogsQL filters a field with `field:"value"` and combines filters with a space or
`AND`. There is no `| json` pipe, so a LogQL query like

```logql
{service_name=~"master-simcore_master_.*"} | json | log_level = `ERROR`
```

fails with `unexpected pipe name "json"`. Pass `format: "compact"` for any query
that can match many lines.

### Logs by log level from all simcore services

```logsql
{service_name=~"master-simcore_master_.*"} AND log_level:"ERROR"
```

Replace `ERROR` with `WARNING`, `INFO` or `DEBUG` to change the level.

### Error logs from one simcore service

```logsql
{service_name="master-simcore_master_webserver"} AND log_level:"ERROR"
```

Replace `webserver` with `api-server`, `director-v2`, `catalog`, `dynamic-schdlr`,
`agent` or `wb-garbage-collector`.

### Text search in one service

```logsql
{service_name="master-simcore_master_webserver"}
  AND _msg:~"(?i)error|exception|traceback"
```

`_msg` holds the log message. A bare `"substring"` filter searches every field.

### Logs with a specific trace ID

```logsql
{service_name=~"master-simcore_master_.*"} AND log_trace_id:"<trace-id>"
```

### Dynamic service logs

```logsql
{service_name=~"dy-proxy_<node-uuid>"}
{service_name=~"dy-sidecar_<node-uuid>"}
```

### Error logs from any service

Traefik, Redis and the other non-simcore services have no structured `log_level`,
so match the message:

```logsql
{source_type="docker_swarm_logs"} AND _msg:~"(?i)error|ERR"
```

## PromQL

On metrics, `service_name` is the bare service name. Container metrics carry the
full Swarm name in `container_label_com_docker_swarm_service_name`.

### HTTP request rate by service

```promql
sum by (service_name) (rate(http_requests_total[5m]))
```

### HTTP error rate

The status label is `http_status`, not `status`:

```promql
sum by (service_name) (rate(http_requests_total{http_status=~"5.."}[5m]))
```

### Request latency p95

The simcore HTTP histogram is `http_request_latency_seconds_with_labels`:

```promql
histogram_quantile(
  0.95,
  sum by (le, service_name) (
    rate(http_request_latency_seconds_with_labels_bucket{service_name="webserver"}[5m])
  )
)
```

### Container memory usage

```promql
sum by (container_label_com_docker_swarm_service_name) (
  container_memory_working_set_bytes{
    container_label_com_docker_swarm_service_name=~"master-simcore_master_.*"
  }
)
```

### Container CPU usage

```promql
sum by (container_label_com_docker_swarm_service_name) (
  rate(container_cpu_usage_seconds_total{
    container_label_com_docker_swarm_service_name=~"master-simcore_master_.*"
  }[5m])
)
```

## Workflow to investigate an error

1. Check for errors in the simcore services:

   ```logsql
   {service_name=~"master-simcore_master_.*"} AND log_level:"ERROR"
   ```

   If this returns nothing, widen the search to all services:

   ```logsql
   {source_type="docker_swarm_logs"} AND _msg:~"(?i)error|ERR"
   ```

2. Narrow down. Log lines written while a request is handled carry a
   `log_trace_id`. Trace all services on that request:

   ```logsql
   {service_name=~"master-simcore_master_.*"} AND log_trace_id:"<trace-id>"
   ```

   When `log_trace_id` is missing, no request handler wrote the line. Filter to
   the one service instead:

   ```logsql
   {service_name="master-simcore_master_<service>"} AND log_level:"ERROR"
   ```

3. Read the surrounding logs with `direction: "forward"` and a narrow window around
   the error timestamp.

4. Fetch the trace by ID when `log_trace_id` is not `"0"`. Its services are named
   `simcore-service-<name>`, so a filter on the log `service_name` will not match.

5. Check the impact: request rate and error rate of that service over the same
   window. Metric `service_name` values are bare (`webserver`).

## Tips

- The default lookback is one hour. Pass `startRfc3339` and `endRfc3339`
  (`now-6h`, `now`) for anything wider.
- `limit` caps the result count (100 maximum for log queries), and
  `format: "compact"` reports each stream's labels once.
- `direction: "backward"` (default) returns newest first, `forward` oldest first.
- `queryType: "instant"` returns one value per metric query, and `stepSeconds` sets
  the resolution of a range query.
- `query_loki_stats` fills `entries` only on this datasource. `streams`, `chunks`
  and `bytes` stay 0.
- `list_loki_label_values` is unbounded here: 57303 `service_name` values without
  a `matcher`, mostly `dy-sidecar_*`, `dy-proxy_*`, `jsonifier_*` and `sleeper_*`
  streams. Always pass `matcher`.

Last updated: 2026-11-18, values verified against master.
