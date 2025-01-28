import pytest
from simcore_service_storage.utils.simcore_s3_dsm_utils import compute_file_id_prefix


@pytest.mark.parametrize(
    "file_id, levels, expected",
    [
        (
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            3,
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c/my",
        ),
        (
            "api/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            3,
            "api/42b9cc07-60f5-4d29-a063-176d1467901c/my",
        ),
    ],
)
def test_compute_file_id_prefix(file_id, levels, expected):
    assert compute_file_id_prefix(file_id, levels) == expected
