import hashlib
import inspect
import json

from ..t_scheduler import WorkflowRegistry
from ._lifespan import _register_workflows


def _source_hash(obj: object) -> str:
    source = inspect.getsource(obj)
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def compute_workflows_signatures() -> str:
    registry = WorkflowRegistry()
    _register_workflows(registry)

    snapshot: dict[str, dict[str, str]] = {"workflows": {}, "activities": {}}

    for wf_cls in registry.all_workflows():
        snapshot["workflows"][wf_cls.__name__] = _source_hash(wf_cls)

    for act_fn in registry.all_activities():
        snapshot["activities"][act_fn.__name__] = _source_hash(act_fn)

    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
