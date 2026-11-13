"""Attributes RabbitMQ broker log lines to the xdist worker that caused them

Workers share one broker, so a warning in its log says nothing until it is pinned to a worker.
RabbitMQ pins it for us: connection-scoped entries name the principals inline, e.g. (RabbitMQ 4.1.6)

    [error] <0.835.0> Channel error on connection <0.826.0> (172.17.0.1:53276 -> 172.17.0.2:5672,
              vhost: 'pytest_gw0', user: 'guest'), channel 1:
    [error] <0.835.0> operation exchange.declare caused a channel exception precondition_failed: ...

Two properties of that format drive this module:

- the continuation line repeats only the reporting pid (`<0.835.0>`), never the principals, so a
  line without them inherits the attribution of the last line reported by the same process. Note
  that pid is a *channel* process here, so it is not in the management API's connection list.
- a broker-wide notice (resource alarms, `rebuilding indices from scratch`) names neither and no
  earlier line shares its pid. Those stay unattributed: nothing in the log ties them to a worker.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

_REPORTING_PID_RE: Final = re.compile(r"<(\d+\.\d+\.\d+)>")
_VHOST_RE: Final = re.compile(r"vhost: '([^']*)'")
_USER_RE: Final = re.compile(r"\buser: '([^']*)'")
# a rejected login happens before the vhost is selected, so this one names only the user
_LOGIN_USER_RE: Final = re.compile(r"\buser '([^']*)'")


@dataclass(frozen=True)
class BrokerLogAttribution:
    """Broker log lines sorted by who caused them"""

    mine: list[str] = field(default_factory=list)
    others: list[str] = field(default_factory=list)
    unattributed: list[str] = field(default_factory=list)


def _names_worker(line: str, worker_user: str, worker_vhost: str) -> bool | None:
    """Whether this line names the given worker, another one, or nobody

    The user wins over the vhost: a line naming this worker's vhost and a different user is the
    admin/health-check connection looking into the vhost, not the worker's own traffic.
    """
    if user := _USER_RE.search(line) or _LOGIN_USER_RE.search(line):
        return user.group(1) == worker_user
    if vhost := _VHOST_RE.search(line):
        return vhost.group(1) == worker_vhost
    return None


def attribute_log_lines(lines: Iterable[str], *, worker_user: str, worker_vhost: str) -> BrokerLogAttribution:
    """Sorts broker log lines into this worker's, another worker's, and nobody's

    Args:
        lines: log lines in the order the broker wrote them
        worker_user: the RabbitMQ user this worker's clients connect with
        worker_vhost: the vhost this worker is confined to

    Returns:
        The lines in three buckets, each in broker order. A line naming a principal is that
        principal's; a line naming none is attributed to whoever the same reporting process said
        last; a line neither names nor follows such a line is unattributed.
    """
    attribution = BrokerLogAttribution()
    owners_by_pid: dict[str, bool] = {}

    for line in lines:
        pid_match = _REPORTING_PID_RE.search(line)
        pid = pid_match.group(1) if pid_match else None

        names = _names_worker(line, worker_user, worker_vhost)
        if names is None and pid is not None:
            names = owners_by_pid.get(pid)
        if names is None:
            attribution.unattributed.append(line)
            continue

        (attribution.mine if names else attribution.others).append(line)
        if pid is not None:
            owners_by_pid[pid] = names

    return attribution
