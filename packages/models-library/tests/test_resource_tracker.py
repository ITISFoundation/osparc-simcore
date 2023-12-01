import pytest
from models_library.resource_tracker import HardwareInfo


@pytest.mark.parametrize(
    "aws_ec2_instances, is_warning_logged",
    [
        (["1", "2"], True),
        (["1"], False),
        ([], False),
    ],
)
def test_hardware_info_warning(
    caplog: pytest.LogCaptureFixture,
    aws_ec2_instances: list[str],
    is_warning_logged: bool,
):
    caplog.clear()
    HardwareInfo(aws_ec2_instances=aws_ec2_instances)

    if is_warning_logged:
        assert "Unexpected number o ec2 instances" in caplog.text
    else:
        assert len(caplog.text) == 0
