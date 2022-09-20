# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.aws_utils import compose_user_data
from simcore_service_autoscaling.core.settings import AwsSettings


def test_compose_user_data(app_environment: EnvVarsDict):

    settings = AwsSettings.create_from_envs()

    user_data = compose_user_data(settings)
    print(user_data)

    for line in user_data.split("\n"):
        if "ssh" in line:
            assert f"ubuntu@{settings.AWS_DNS}" in line
