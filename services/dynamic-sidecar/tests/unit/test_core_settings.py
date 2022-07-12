# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings


def test_settings_with_mock_environment(mock_environment):
    assert ApplicationSettings.create_from_envs()


def test_settings_with_envdevel_file(mock_environment_with_envdevel):
    assert ApplicationSettings.create_from_envs()
