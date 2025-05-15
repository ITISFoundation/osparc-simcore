import distributed

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test_scheduler(dask_client: distributed.Client) -> None:
    assert True
