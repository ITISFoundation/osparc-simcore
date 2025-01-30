# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_efs_guardian.core.settings import ApplicationSettings


def test_settings(app_environment: EnvVarsDict):
    """
    We validate actual envfiles (e.g. repo.config files) by passing them via the CLI

    $ ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
    $ pytest --external-envfile=.secrets --pdb tests/unit/test_core_settings.py

    """
    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()
    assert settings.EFS_GUARDIAN_POSTGRES
