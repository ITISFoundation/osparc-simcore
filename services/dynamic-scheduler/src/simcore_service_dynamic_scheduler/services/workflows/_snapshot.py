import hashlib
import inspect
from collections.abc import Callable
from typing import Any

from common_library.json_serialization import json_dumps

from ..t_scheduler import WorkflowRegistry
from ._lifespan import _register_workflows


def _source_hash(obj: type[Any] | Callable[..., Any]) -> str:
    source = inspect.getsource(obj)
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def compute_workflows_signatures() -> str:
    registry = WorkflowRegistry()
    _register_workflows(registry)

    snapshot: dict[str, dict[str, str]] = {"workflows": {}, "activities": {}}

    for name, wf_cls in registry.get_registered_workflows().items():
        snapshot["workflows"][name] = _source_hash(wf_cls)
        for act_fn in wf_cls.get_activities():
            snapshot["activities"][f"{name}.{act_fn.__name__}"] = _source_hash(act_fn)

    return json_dumps(snapshot, indent=2, sort_keys=True) + "\n"
