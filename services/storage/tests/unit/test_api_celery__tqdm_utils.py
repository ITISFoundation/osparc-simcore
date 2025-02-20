from time import sleep

from simcore_service_storage.api.celery._tqdm_utils import (
    get_export_progress,
    set_absolute_progress,
)


def test_get_export_progess():
    items = 10
    with get_export_progress(total=1, description="test") as pbar:
        # Run tasks and call the callback each time
        for k in [i / (items - 1) for i in range(items)]:
            sleep(0.01)
            set_absolute_progress(pbar, current_progress=k)
