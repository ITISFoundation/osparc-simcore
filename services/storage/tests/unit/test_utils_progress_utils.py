from time import sleep

from models_library.progress_bar import ProgressReport
from simcore_service_storage.utils.progress_utils import (
    get_tqdm_progress,
    set_tqdm_absolute_progress,
)


def test_tqdm_progress_utils():
    items = 10
    with get_tqdm_progress(total=1, description="test") as pbar:
        # Run tasks and call the callback each time
        for k in [i / (items - 1) for i in range(items)]:
            sleep(0.01)
            set_tqdm_absolute_progress(pbar, ProgressReport(actual_value=k))
            assert pbar.n == k
