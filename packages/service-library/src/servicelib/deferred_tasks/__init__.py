"""
# SEE original PR https://github.com/ITISFoundation/osparc-simcore/pull/5704

The `BaseDeferredHandler` is the interface to the user.
(**note:** "states" are defined in the diagram below in the rectangles)


- `get_retries` (used by state`Scheduled`) [default 1] {can br overwritten by the user}:
    returns the max attempts to retry user code
- `get_timeout` (used by state`Scheduled`) [required] {MUST be implemented by user}:
    timeout for running the user code
- `start` (called by the user) [required] {MUST be implemented by user}:
    defines a nice entrypoint to start new tasks
- `on_created` (called after `start` executes) [optional] {can be overwritten by the user}:
    provides a global identifier for the started task
- `run` (called by state `Worker`) [required] {MUST be implemented by user}:
    code the user wants to run
- `on_result` (called by state `DeferredResult`) [required] {MUST be implemented by user}:
    provides the result of an execution
- `on_finished_with_error` (called by state `FinishedWithError`) [optional] {can be overwritten by the user}:
    react to execution error, only triggered if all retry attempts fail
- `cancel`: (called by the user) [optional]:
    send a message to cancel the current task. A warning will be logged but no call to either
    `on_result` or `on_finished_with_error` will occur.


## DeferredHandler lifecycle

```mermaid
stateDiagram-v2
    * --> Scheduled: via [start]
    ** --> ManuallyCancelled: via [cancel]

    ManuallyCancelled --> Worker: attempts to cancel task in

    Scheduled --> SubmitTask
    SubmitTask --> Worker

    ErrorResult --> SubmitTask: try again
    Worker --> ErrorResult: upon error
    ErrorResult --> FinishedWithError: gives up when out of retries or if cancelled
    Worker --> DeferredResult: success

    DeferredResult --> °: calls [on_result]
    FinishedWithError --> °°: calls [on_finished_with_error]
    Worker --> °°°: task cancelled
```

### States

Used internally for scheduling the task's execution:

- `Scheduled`: triggered by `start` and creates a schedule for the task
- `SubmitTask`: decreases retry counter
- `Worker`: checks if enough workers slots are available (can refuse task), creates from `run` code and saves the result.
- `ErrorResult`: checks if it can reschedule the task or gives up
- `FinishedWIthError`: logs error, invokes `on_finished_with_error` and removes the schedule
- `DeferredResult`: invokes `on_result` and removes the schedule
- `ManuallyCancelled`: sends message to all instances to cancel. The instance handling the task will cancel the task and remove the schedule
"""

from ._base_deferred_handler import (
    BaseDeferredHandler,
    DeferredContext,
    GlobalsContext,
    StartContext,
)
from ._deferred_manager import DeferredManager
from ._models import TaskResultError, TaskUID

__all__: tuple[str, ...] = (
    "BaseDeferredHandler",
    "DeferredContext",
    "DeferredManager",
    "GlobalsContext",
    "StartContext",
    "TaskResultError",
    "TaskUID",
)
