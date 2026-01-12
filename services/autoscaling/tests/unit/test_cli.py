# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from simcore_service_autoscaling.cli import main
from typer.testing import CliRunner

pytest_simcore_core_services_selection = [
    "docker-api-proxy",
]

runner = CliRunner()


def test_settings(setup_docker_api_proxy: None):
    result = runner.invoke(main, ["settings"])
    assert result.exit_code == 0
    assert "APP_NAME=simcore-service-autoscaling" in result.stdout


def test_run(setup_docker_api_proxy: None):
    result = runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout
