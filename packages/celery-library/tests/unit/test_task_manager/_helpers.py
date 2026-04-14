"""Compatibility shim for legacy ``test_task_manager`` helpers.

The canonical shared test helpers live in ``tests/unit/task_manager/conftest.py``.
This module re-exports them so there is a single source of truth and no duplicated
helper/task implementations to maintain.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_canonical_helpers_module():
    helpers_path = Path(__file__).resolve().parents[1] / "task_manager" / "conftest.py"
    spec = spec_from_file_location("_task_manager_conftest", helpers_path)
    if spec is None or spec.loader is None:
        msg = f"Cannot load canonical task-manager helpers from {helpers_path}"
        raise ImportError(msg)

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CANONICAL_HELPERS = _load_canonical_helpers_module()

_fake_file_processor = _CANONICAL_HELPERS._fake_file_processor
fake_file_processor = _CANONICAL_HELPERS.fake_file_processor
MyError = _CANONICAL_HELPERS.MyError
failure_task = _CANONICAL_HELPERS.failure_task
dreamer_task = _CANONICAL_HELPERS.dreamer_task
streaming_results_task = _CANONICAL_HELPERS.streaming_results_task
wait_for_task_success = _CANONICAL_HELPERS.wait_for_task_success
wait_for_task_done = _CANONICAL_HELPERS.wait_for_task_done

__all__ = [
    "_fake_file_processor",
    "fake_file_processor",
    "MyError",
    "failure_task",
    "dreamer_task",
    "streaming_results_task",
    "wait_for_task_success",
    "wait_for_task_done",
]
