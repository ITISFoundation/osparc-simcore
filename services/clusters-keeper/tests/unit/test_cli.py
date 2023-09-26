# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from faker import Faker
from simcore_service_clusters_keeper.cli import main
from typer.testing import CliRunner

runner = CliRunner()


def test_settings(monkeypatch: pytest.MonkeyPatch, faker: Faker):
    monkeypatch.setenv("SWARM_STACK_NAME", faker.pystr())
    result = runner.invoke(main, ["settings"])
    assert result.exit_code == 0
    assert "APP_NAME=simcore-service-clusters-keeper" in result.stdout


def test_run():
    result = runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout
