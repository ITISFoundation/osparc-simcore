# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from simcore_service_clusters_keeper.cli import main
from typer.testing import CliRunner

runner = CliRunner()


def test_settings():
    result = runner.invoke(main, ["settings"])
    assert result.exit_code == 0
    assert "APP_NAME=simcore-service-clusters-keeper" in result.stdout


def test_run():
    result = runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout
