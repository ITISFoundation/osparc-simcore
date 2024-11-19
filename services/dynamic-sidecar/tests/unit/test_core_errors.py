# pylint:disable=broad-exception-caught
# pylint:disable=no-member

from simcore_service_dynamic_sidecar.core.errors import (
    UnexpectedDockerError,
    VolumeNotFoundError,
)
from starlette import status


def test_legacy_interface_unexpected_docker_error():
    message = "some_message"
    status_code = 42
    try:
        raise UnexpectedDockerError(  # noqa: TRY301
            message=message, status_code=status_code
        )
    except Exception as e:
        print(e)
        assert e.status_code == status_code  # noqa: PT017
        assert message in e.message  # noqa: PT017


def test_legacy_interface_volume_not_found_error():
    try:
        volumes = [{}, {"Name": "a_volume"}]
        volume_names = " ".join(v.get("Name", "UNKNOWN") for v in volumes)

        raise VolumeNotFoundError(  # noqa: TRY301
            volume_count=len(volumes),
            source_label="some",
            run_id="run_id",
            volume_names=volume_names,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        print(e)
        assert (  # noqa: PT017
            e.message
            == "Expected 1 got 2 volumes labels with source_label=some, run_id=run_id: Found UNKNOWN a_volume"
        )
        assert e.status_code == status.HTTP_404_NOT_FOUND  # noqa: PT017
