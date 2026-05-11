# Simcore Log Structure

## Overview

All simcore service logs are shipped via **Vector** to Loki as JSON. Each log line is a JSON object with two layers:
1. **Container metadata** — added by the log shipper (Vector)
2. **Application log fields** — structured fields from the Python logging framework

## Full JSON Schema

```json
{
  // --- Container/shipping metadata ---
  "_command": "services/web/server/docker/entrypoint.sh ...",
  "_container_id": "<docker container id>",
  "_container_name": "<stack>_<prefix>_webserver.2.nfwzd0qiwykqhaelbln0fl7fn",
  "_image_id": "sha256:...",
  "_image_name": "itisfoundation/webserver:<tag>@sha256:...",
  "_tag": "<short container id>",
  "container_id": "<docker container id>",
  "container_name": "<stack>_<prefix>_webserver.2.nfwzd0qiwykqhaelbln0fl7fn",
  "host": "<swarm-node-hostname>",
  "image_name": "itisfoundation/webserver:<tag>@sha256:...",
  "port": 38000,
  "processed_by": "vector",
  "service_name": "<stack>_<prefix>_webserver",
  "source_type": "socket",
  "version": "1.1",

  // --- Application-level fields ---
  "level": "INFO",
  "log_level": "INFO",
  "log_timestamp": "2026-04-30 15:33:00,806",
  "log_source": "gunicorn.access:log(214)",
  "log_uid": "None",
  "log_oec": "None",
  "log_trace_id": "0",
  "log_span_id": "0",
  "log_trace_sampled": "False",
  "log_service": "<stack>_<prefix>_webserver",
  "log_msg": "172.23.0.38 [30/Apr/2026:15:33:00 +0000] \"GET /metrics HTTP/1.1\" 200 280152 [137000us] \"-\" \"Prometheus/3.5.1\"",
  "message": "log_level=INFO | log_timestamp=2026-04-30 15:33:00,806 | log_source=gunicorn.access:log(214) | ..."
}
```

## Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `log_level` | string | Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `level` | string | Duplicate of log_level (some services use this instead) |
| `log_timestamp` | string | Timestamp from the application (`YYYY-MM-DD HH:MM:SS,mmm`) |
| `log_source` | string | Python module and function: `module.submodule:function(line)` |
| `log_msg` | string | The actual log message content |
| `log_uid` | string | User ID associated with the request (or `"None"`) |
| `log_oec` | string | Operation Error Code for error categorization (or `"None"`) |
| `log_trace_id` | string | OpenTelemetry trace ID (or `"0"` if not traced) |
| `log_span_id` | string | OpenTelemetry span ID (or `"0"` if not traced) |
| `log_trace_sampled` | string | Whether the trace is sampled (`"True"`/`"False"`) |
| `log_service` | string | Service name from the application's perspective |
| `service_name` | string | Loki stream label — the service identifier |
| `container_name` | string | Full Docker container name with replica and task ID |
| `host` | string | Docker Swarm node hostname |
| `message` | string | Full formatted log line (pipe-separated key=value pairs) |

## Non-simcore Services (Traefik, Redis, etc.)

Services that don't use the simcore Python logging framework have a simpler structure:

```json
{
  // Container metadata (same as above)
  "level": "UNKNOWN",
  "log_msg": "<raw log line from the service>",
  "log_service": "<stack>_<prefix>_traefik",
  "message": "<raw log line from the service>"
}
```

For these services, the `level` field is typically `"UNKNOWN"` and the actual severity must be parsed from the `log_msg` content (e.g., Traefik uses ANSI-colored `WRN`, `ERR`, `INF` markers).

## Container Name Format

```
<stack>_<prefix>_<service>.<replica>.<task_id>
```

The `<stack>` and `<prefix>` vary by deployment (e.g., `simcore_staging`, `simcore_production`). Discover the actual pattern by listing `service_name` label values in Loki.

Example: `simcore_staging_webserver.2.nfwzd0qiwykqhaelbln0fl7fn`
- Service: `webserver`
- Replica: `2` (second instance)
- Task ID: `nfwzd0qiwykqhaelbln0fl7fn` (Docker Swarm task)

## Notes on Log Level Filtering

- For **simcore Python services**: Use `| json | log_level = \`ERROR\`` or filter with `|= "\"log_level\":\"ERROR\""` in the raw line
- For **non-Python services** (traefik, redis): Use text matching like `|~ "(?i)error"` since they don't have structured `log_level`
- The `level` field from Vector processing may not be reliable for all services — prefer `log_level` for simcore services
- If `log_level` filtering returns no results but you expect errors, try the broader `|~ "(?i)error|exception|traceback|critical"` filter which catches both structured and unstructured error indicators
