# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path


def test_minimal_folder_layout(service_under_test_dir: Path):
    assert service_under_test_dir.exists()

    # has osparc folder
    assert any(service_under_test_dir.glob(".osparc/**/metadata.yml"))

    # has validation folder # TODO: define path in .osparc??
    assert (service_under_test_dir / "validation").exists()
    assert (service_under_test_dir / "validation" / "input").exists()
    assert (service_under_test_dir / "validation" / "output").exists()
