import pytest
from models_library.resource_tracker import HardwareInfo
from pydantic import ValidationError


@pytest.mark.parametrize(
    "aws_ec2_instances, raises_error",
    [
        (["1", "2"], True),
        (["1"], False),
        ([], False),
    ],
)
def test_hardware_info_warning(aws_ec2_instances: list[str], raises_error: bool):
    if raises_error:
        with pytest.raises(ValidationError, match="Only 1 entry is supported"):
            HardwareInfo(aws_ec2_instances=aws_ec2_instances)
    else:
        HardwareInfo(aws_ec2_instances=aws_ec2_instances)
