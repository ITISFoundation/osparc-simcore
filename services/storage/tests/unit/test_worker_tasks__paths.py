import asyncio
from pathlib import Path
from unittest import mock

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from simcore_service_storage.api._worker_tasks import _paths as paths_worker_tasks


async def test_delete_paths_completes_in_flight_children_before_raising(monkeypatch):
    """When one delete fails, the siblings must still run to completion (their
    connection cleanup) before the error is raised: reraise=True would abandon
    them and leak their pooled database connections
    """
    failing_path = Path("11111111-1111-1111-1111-111111111111/node/file.txt")
    slow_path = Path("22222222-2222-2222-2222-222222222222/node/file.txt")
    completed_paths: list[Path] = []

    async def delete_path(user_id: UserID, path: Path):
        try:
            if path == failing_path:
                message = "no access to file"
                raise FileNotFoundError(message)
            await asyncio.sleep(0.05)
        finally:
            completed_paths.append(path)

    dsm = mock.MagicMock()
    dsm.delete_path = delete_path
    dsm_provider = mock.MagicMock()
    dsm_provider.get.return_value = dsm
    monkeypatch.setattr(paths_worker_tasks, "get_app_server", lambda _app: mock.MagicMock())
    monkeypatch.setattr(paths_worker_tasks, "get_dsm_provider", lambda _app: dsm_provider)

    with pytest.raises(FileNotFoundError):
        await paths_worker_tasks.delete_paths(
            task=mock.MagicMock(),
            task_key="task-key",
            user_id=UserID(1),
            product_name=ProductName("osparc"),
            location_id=0,
            paths={failing_path, slow_path},
        )

    # the sibling that was still in flight at the error must have completed,
    # otherwise its pooled connection cleanup would never run
    assert set(completed_paths) == {failing_path, slow_path}
