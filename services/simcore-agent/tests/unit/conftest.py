from pathlib import Path

import pytest
import simcore_service_simcore_agent


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "simcore-agent"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_simcore_agent"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_simcore_agent.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath
