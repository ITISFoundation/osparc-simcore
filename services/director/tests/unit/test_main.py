# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict


def test_main_app(app_environment: EnvVarsDict):
    from simcore_service_director.main import app_factory  # noqa: PLC0415

    app_factory()
