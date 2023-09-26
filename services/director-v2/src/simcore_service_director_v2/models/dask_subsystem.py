from enum import Enum


# NOTE: mypy fails with src/simcore_service_director_v2/modules/dask_client.py:101:5: error: Dict entry 0 has incompatible type "str": "auto"; expected "Any": "DaskClientTaskState"  [dict-item]
# when using StrAutoEnum
class DaskClientTaskState(str, Enum):
    PENDING = "PENDING"
    NO_WORKER = "NO_WORKER"
    PENDING_OR_STARTED = "PENDING_OR_STARTED"
    LOST = "LOST"
    ERRED = "ERRED"
    ABORTED = "ABORTED"
    SUCCESS = "SUCCESS"
