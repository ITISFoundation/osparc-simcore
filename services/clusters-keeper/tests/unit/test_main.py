# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pytest_simcore.helpers.utils_envs import EnvVarsDict


def test_main_app(app_environment: EnvVarsDict):
    from simcore_service_clusters_keeper.main import the_app, the_settings

    assert the_app.state.settings == the_settings
