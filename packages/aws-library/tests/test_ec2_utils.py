from aws_library.ec2._utils import compose_user_data
from faker import Faker


def test_compose_user_data(faker: Faker):
    """Test default (cold-start) user data format: plain bash script."""
    script = faker.pystr()
    user_data = compose_user_data(script, run_on_every_boot=False)
    assert user_data.startswith("#!/bin/bash\n")
    assert script in user_data
    assert user_data.endswith("\n")


def test_compose_user_data_run_on_every_boot(faker: Faker):
    """Test warm buffer (per-boot) user data format: MIME multi-part."""
    script = faker.pystr()
    user_data = compose_user_data(script, run_on_every_boot=True)

    # Check MIME multi-part structure
    assert user_data.startswith("MIME-Version: 1.0\n")
    assert "Content-Type: multipart/mixed; boundary=" in user_data
    assert "===============SIMCORE_BOUNDARY==" in user_data
    assert "text/x-shellscript-per-boot" in user_data

    # Check that script is included
    assert script in user_data

    # Check proper MIME boundaries
    assert user_data.count("--===============SIMCORE_BOUNDARY==") == 2  # Start and end
    assert user_data.endswith("--===============SIMCORE_BOUNDARY==--\n")
