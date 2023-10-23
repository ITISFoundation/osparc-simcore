# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_clusters_keeper.core.settings import ApplicationSettings


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.CLUSTERS_KEEPER_EC2_ACCESS
    assert settings.CLUSTERS_KEEPER_EC2_INSTANCES
    assert settings.CLUSTERS_KEEPER_RABBITMQ
    assert settings.CLUSTERS_KEEPER_REDIS
    assert settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES
