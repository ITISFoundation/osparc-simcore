# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings


def test_settings_with_mock_environment(mock_environment):
    assert DynamicSidecarSettings.create_from_envs()


def test_settings_with_envdevel_file(mock_environment_with_envdevel):
    assert DynamicSidecarSettings.create_from_envs()
