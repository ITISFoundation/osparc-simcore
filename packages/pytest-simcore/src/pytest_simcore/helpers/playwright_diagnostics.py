"""Failure diagnostics: what a stalled pipeline means and how to ask the backend about it."""

import json
import urllib.parse
from datetime import datetime
from typing import Annotated, Any, Final

from annotated_types import doc
from models_library.api_schemas_directorv2.computations import ComputationGet
from models_library.projects_state import RunningState
from playwright.sync_api import (
    APIRequestContext,
)
from pydantic import AnyUrl

from .playwright_constants import SECOND

# NOTE: names follow `RunningState`'s own definitions (models_library/projects_state.py), since a
# timeout means something different in each state. PENDING is left out of the first group: a task
# only reaches it once director-v2 got a job id back from the scheduler, so it is a no-worker symptom
_STATES_NEVER_SENT_TO_SCHEDULER: Final[
    Annotated[
        tuple[RunningState, ...],
        doc("the backend accepted the computation but has not handed any task to the Dask scheduler"),
    ]
] = (RunningState.PUBLISHED,)

_NEVER_SENT_TO_SCHEDULER_HINT: Final[
    Annotated[
        str,
        doc("appended when the pipeline times out in PUBLISHED: a frequent cause is an unreachable dask-scheduler"),
    ]
] = (
    "HINT: the backend accepted the pipeline but never scheduled it: check director-v2 logs "
    "(DaskClientAcquisisitonError) and that the dask-scheduler service has running replicas"
)

_STATES_WAITING_FOR_A_WORKER: Final[
    Annotated[
        tuple[RunningState, ...],
        doc("the scheduler holds the task but no worker took it; PENDING is also a transition state"),
    ]
] = (RunningState.PENDING, RunningState.WAITING_FOR_RESOURCES)

_NO_WORKER_HINT: Final[
    Annotated[
        str,
        doc("appended when a task the scheduler accepted never starts running"),
    ]
] = (
    "HINT: no worker picked the task up: check the dask-sidecar services and the autoscaling service "
    "(PENDING can also be a transition state while director-v2 asks for a cluster)"
)

_STATES_WAITING_FOR_A_CLUSTER: Final[
    Annotated[
        tuple[RunningState, ...],
        doc("no Dask scheduler is available and none became available"),
    ]
] = (RunningState.WAITING_FOR_CLUSTER,)

_NO_CLUSTER_HINT: Final[
    Annotated[
        str,
        doc("appended when the pipeline waits for a scheduler that never arrives"),
    ]
] = (
    "HINT: no dask-scheduler is available to run the task: check the autoscaling, clusters-keeper "
    "and dask-scheduler services"
)


def _pipeline_wait_raised_message(
    state: RunningState,
    expected_states: tuple[RunningState, ...],
    *,
    timed_out: bool,
) -> str:
    """The `log_context` failure message for a pipeline wait.

    The hints describe a wait that ran out of time, so any other error (a websocket that never
    connected or could not be reattached) says nothing about the backend and gets no hint.
    """
    message = f"pipeline failed or timed out with {state}. Expected one of {expected_states=}"
    if not timed_out:
        return message
    if state in _STATES_NEVER_SENT_TO_SCHEDULER:
        return f"{message}. {_NEVER_SENT_TO_SCHEDULER_HINT}"
    if state in _STATES_WAITING_FOR_A_WORKER:
        return f"{message}. {_NO_WORKER_HINT}"
    if state in _STATES_WAITING_FOR_A_CLUSTER:
        return f"{message}. {_NO_CLUSTER_HINT}"
    return message


def classify_backend_stall(
    state: RunningState,
    node_statuses: dict[str, RunningState],
) -> list[str]:
    """Hints about why a computation is stuck, derived from what the backend itself reports.
    `node_statuses` maps each node id to its state on the backend.
    """
    hints: list[str] = []
    if state in _STATES_NEVER_SENT_TO_SCHEDULER:
        # NOTE: publishing a run marks its tasks PUBLISHED, so a task with no job id is reported as
        # NOT_STARTED or PUBLISHED. Anything further along means it reached the scheduler.
        # An empty node_statuses has no task to schedule and must not be blamed on scheduling.
        not_sent_to_scheduler = (RunningState.NOT_STARTED, RunningState.PUBLISHED)
        if node_statuses and all(status in not_sent_to_scheduler for status in node_statuses.values()):
            hints.append(_NEVER_SENT_TO_SCHEDULER_HINT)
    elif state in _STATES_WAITING_FOR_A_WORKER:
        hints.append(_NO_WORKER_HINT)
    elif state in _STATES_WAITING_FOR_A_CLUSTER:
        hints.append(_NO_CLUSTER_HINT)
    if state == RunningState.FAILED:
        failed_nodes = sorted(node_id for node_id, status in node_statuses.items() if status == RunningState.FAILED)
        if failed_nodes:
            hints.append(f"HINT: these nodes failed on the backend: {failed_nodes}, fetch their logs from director-v2")
    return hints


def backend_computation_snapshots(response_body: Any) -> dict[str, dict[str, Any]]:
    """What the backend reports about a computation, from the body of a
    `GET /v0/computations/{project_id}` request, keyed by computation id.

    The web-server answers with a list with one entry per runnable variant of the project (see
    `get_computation` in the web-server's director_v2 controller), so a stalled variant is not
    necessarily the first one.

    NOTE: the web-server builds the payload with `model_construct` and dumps it with
    `exclude_unset=True`, so a field director-v2 never sets is simply missing. Since `iteration`,
    `started`, `stopped` and `submitted` are required, a partial entry fails validation: the
    snapshot of a project is all-or-nothing.
    """
    snapshots: dict[str, dict[str, Any]] = {}
    for entry in response_body["data"]:
        computation = ComputationGet.model_validate(entry)
        node_statuses: dict[str, RunningState] = {
            f"{node_id}": node_state.current_status
            for node_id, node_state in computation.pipeline_details.node_states.items()
        }
        snapshots[f"{computation.id}"] = {
            "state": computation.state.value,
            "result": computation.result,
            "node_statuses": {node_id: status.value for node_id, status in node_statuses.items()},
            "stall_hints": classify_backend_stall(computation.state, node_statuses),
        }
    if not snapshots:
        msg = "the backend reported no computation for this project"
        raise LookupError(msg)
    return snapshots


DEFAULT_GRAFANA_LOGS_DATASOURCE_UID: Final[
    Annotated[str, doc("VictoriaLogs datasource of the deployments this suite runs against today")]
] = "victoria-logs"

# NOTE: log streams are named `<stack>_<compose service name>` (see the grafana-query skill), and the
# stack prefix is unknown at test time, hence the leading `.*_`. The names are those of
# services/docker-compose.yml: the web-server runs as `webserver`, its db-listener as
# `wb-db-event-listener`.
FAILURE_DIAGNOSIS_LOG_SERVICES: Final[tuple[str, ...]] = (
    "api-server",
    "autoscaling",
    "dask-scheduler",
    "dask-sidecar",
    "director-v2",
    "wb-db-event-listener",
    "webserver",
)

FAILURE_DIAGNOSIS_LOGS_QUERY: Final[Annotated[str, doc("LogsQL over the services implicated in a pipeline stall")]] = (
    '{service_name=~".*_(' + "|".join(FAILURE_DIAGNOSIS_LOG_SERVICES) + ')"}'
)

_BACKEND_SNAPSHOT_TIMEOUT_MS: Final[
    Annotated[int, doc("bound for a diagnostic GET against a deployment that is unhealthy by definition")]
] = 5 * SECOND


def capture_backend_computation(
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    project_id: str,
    *,
    timeout_ms: int = _BACKEND_SNAPSHOT_TIMEOUT_MS,
) -> dict[str, Any]:
    """What the backend reports about `project_id`. Any failure becomes an error entry, because it
    must neither mask the test's own error nor skip stopping the computation."""
    try:
        response = api_request_context.get(f"{product_url}v0/computations/{project_id}", timeout=timeout_ms)
        if not response.ok:
            msg = f"HTTP {response.status}: {response.text()[:200]}"
            raise RuntimeError(msg)  # noqa: TRY301
        return backend_computation_snapshots(response.json())
    except Exception as err:  # pylint: disable=broad-exception-caught
        return {"error": repr(err)[:500]}


def normalize_grafana_base_url(value: Any) -> str | None:
    """Origin and path prefix of a Grafana URL, with any query or fragment dropped. None when
    `value` is empty or is not a parseable absolute URL.
    """
    if not value:
        return None
    try:
        # NOTE: a URL copied from an address bar often carries ?orgId=..., which would end up in the
        # middle of the explore link; only the origin and any path prefix are needed here
        parsed = urllib.parse.urlsplit(str(value))
        if not parsed.scheme or not parsed.netloc:
            return None
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
    except ValueError:
        return None


def grafana_explore_url(
    grafana_base_url: str,
    *,
    datasource_uid: str,
    query: str,
    start_time: datetime,
    end_time: datetime,
) -> str:
    """Grafana explore link showing `query` on `datasource_uid` between `start_time` and `end_time`"""
    pane = {
        "datasource": datasource_uid,
        "queries": [{"refId": "A", "expr": query, "queryType": "range"}],
        "range": {"from": int(start_time.timestamp() * 1000), "to": int(end_time.timestamp() * 1000)},
    }
    left = urllib.parse.quote(json.dumps(pane, separators=(",", ":")))
    return f"{grafana_base_url}/explore?left={left}"
