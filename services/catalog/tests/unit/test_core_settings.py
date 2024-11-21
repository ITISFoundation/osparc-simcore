# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_catalog.core.settings import ApplicationSettings


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    """
    We can validate actual .env files (also refered as `repo.config` files) by passing them via the CLI

    $ ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
    $ pytest --external-envfile=.secrets --pdb tests/unit/test_core_settings.py

    """
    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()
