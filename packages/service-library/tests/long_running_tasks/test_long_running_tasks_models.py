from servicelib.long_running_tasks.models import TaskProgress


def test_progress_has_no_more_than_3_digits():
    progress = TaskProgress(percent=0.45646)
    assert progress.percent == 0.456
