import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from simcore_service_storage.modules.datcore_adapter import datcore_adapter


@pytest.mark.parametrize(
    "cursor, expected_offset, expected_next_cursor",
    [
        (None, 0, '{"next_page":2,"size":50}'),
        ('{"next_page":2,"size":50}', 50, None),
    ],
)
async def test_list_datasets_accepts_datcore_pagination_response(
    mocker: MockerFixture,
    cursor: str | None,
    expected_offset: int,
    expected_next_cursor: str | None,
):
    api_secret = f"{mocker.sentinel.api_secret}"
    request_mock = mocker.patch.object(
        datcore_adapter,
        "request",
        autospec=True,
        return_value={
            "items": [
                {
                    "display_name": "My dataset",
                    "id": "N:dataset:12345678-1234-1234-1234-123456789abc",
                    "size": None,
                }
            ],
            "limit": 50,
            "offset": expected_offset,
            "total": 51,
        },
    )

    datasets, next_cursor, total = await datcore_adapter.list_datasets(
        FastAPI(),
        api_key="api-key",
        api_secret=api_secret,
        cursor=cursor,
        limit=50,
    )

    assert [dataset.model_dump() for dataset in datasets] == [
        {
            "dataset_id": "N:dataset:12345678-1234-1234-1234-123456789abc",
            "display_name": "My dataset",
        }
    ]
    assert next_cursor == expected_next_cursor
    assert total == 51
    request_mock.assert_awaited_once_with(
        mocker.ANY,
        "api-key",
        api_secret,
        "GET",
        "/datasets",
        params={"limit": 50, "offset": expected_offset},
    )
