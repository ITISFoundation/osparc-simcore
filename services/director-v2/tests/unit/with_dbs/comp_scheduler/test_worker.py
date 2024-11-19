from fastapi import FastAPI
from simcore_service_director_v2.modules.comp_scheduler._worker import (
    _get_scheduler_worker,
)


async def test_worker_starts_and_stops(initialized_app: FastAPI):
    assert _get_scheduler_worker(initialized_app) is not None
