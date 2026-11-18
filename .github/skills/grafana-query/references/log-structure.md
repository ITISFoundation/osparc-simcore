# Simcore Log Structure

## Overview

Simcore service logs arrive in VictoriaLogs as Docker Swarm container logs
(`source_type="docker_swarm_logs"`). VictoriaLogs indexes the fields, so a query
filters on them directly and needs no parsing pipe. Each entry has two layers:

1. container metadata: `service_name`, `container_name`, `container_id`, `host`,
   `source_type`
2. application fields written by the Python logging framework: `log_level`,
   `log_timestamp`, `log_source`, `log_msg`, `log_uid`, `log_oec`,
   `log_trace_id`, `log_span_id`, `log_trace_sampled`, `log_service`

## Field Layout

The log tools report the stream labels and the fields constant across a stream once
per stream, and the per-line fields with each line. Values below are placeholders.

```json
{
  "labels": {
    "container_id": "<container-id>",
    "service_name": "master-simcore_master_webserver",
    "source_type": "docker_swarm_logs"
  },
  "parsed": {
    "container_name": "master-simcore_master_webserver.<replica>.<task-id>",
    "host": "<swarm-node-hostname>",
    "level": "3",
    "log_level": "INFO",
    "log_oec": "None",
    "log_service": "master-simcore_master_webserver",
    "log_trace_sampled": "True",
    "log_uid": "None"
  },
  "lines": [
    {
      "timestamp": "<unix-nanoseconds>",
      "line": "<log message>",
      "parsed": {
        "log_source": "<module>.<submodule>:<function>(<line>)[MainProcess/MainThread]",
        "log_span_id": "<span-id>",
        "log_timestamp": "<YYYY-MM-DD HH:MM:SS,mmm>",
        "log_trace_id": "<trace-id>",
        "message": "log_level=INFO | log_source=... | log_msg=<log message>"
      }
    }
  ]
}
```

## Key Fields

| Field | Kind | Description |
| --- | --- | --- |
| `log_level` | string | Python log level (DEBUG to CRITICAL) |
| `log_timestamp` | string | application timestamp |
| `log_source` | string | module, function and line, plus process and thread |
| `_msg` | field | log message, the target of LogsQL text filters |
| `log_msg` | string | log message content, inside `message` |
| `log_uid` | string | user ID of the request, or `"None"` |
| `log_oec` | string | Operation Error Code, or `"None"` |
| `log_trace_id` | string | OpenTelemetry trace ID, or `"0"` if not traced |
| `log_span_id` | string | OpenTelemetry span ID, or `"0"` if not traced |
| `log_trace_sampled` | string | whether the trace is sampled |
| `log_service` | string | service name as the application reports it |
| `service_name` | label | stream label, the service identifier |
| `container_name` | label | container name with replica and task ID |
| `host` | label | Swarm node hostname |
| `source_type` | label | log pipeline source |
| `level` | label | numeric syslog priority, does not mirror `log_level` |
| `message` | string | full log line as pipe-separated key=value pairs |

Kubernetes workloads (the monitoring and logging stacks) carry `kubernetes.*` labels
instead: `kubernetes.container_name`, `kubernetes.pod_name`,
`kubernetes.pod_namespace`, `kubernetes.pod_node_name`.

## Non-simcore Services

Services that do not use the simcore Python logger (Traefik, Redis) have the
container labels plus one raw message:

```json
{
  "container_name": "master-simcore_master_traefik.<replica>.<task-id>",
  "host": "<swarm-node-hostname>",
  "level": "6",
  "log_service": "master-simcore_master_traefik",
  "message": "2026-01-01T00:00:00Z WRN Health check failed. ... serviceName=<swarm-service>@swarm"
}
```

There is no `log_level` field and the message carries ANSI colour codes, so match
the severity from the text. Traefik writes `WRN`, `ERR` and `INF`.

## Container Name Format

```text
<stack>_<prefix>_<service>.<replica>.<task-id>
```

The `<stack>` and `<prefix>` vary by deployment; on master they are
`master-simcore_master`. Discover the pattern by listing `service_name` label
values with a `matcher`.

For `master-simcore_master_webserver.<replica>.<task-id>`, the service is
`webserver`, the replica is a Swarm replica number, and the last segment is the
Swarm task ID. A service deployed without a mode count shows the Swarm service ID
in the middle segment instead of a replica number.

## Notes on Log Level Filtering

- For simcore Python services, filter the indexed field: `AND log_level:"ERROR"`
- For non-Python services (Traefik, Redis) match the text instead, since they have
  no `log_level`: `AND _msg:~"(?i)error|ERR"`
- `level` is a numeric syslog priority and does not mirror `log_level`. Prefer
  `log_level`.
- If filtering by `log_level` returns nothing where errors are expected, widen to
  `AND _msg:~"(?i)error|exception|traceback|critical"`, which catches structured
  and unstructured indicators alike

Last updated: 2026-11-18, values verified against master.
