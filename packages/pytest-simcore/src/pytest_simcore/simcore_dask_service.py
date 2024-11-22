# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import distributed
import pytest
from distributed import Client
from models_library.clusters import InternalClusterAuthentication, TLSAuthentication
from pydantic import AnyUrl

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip


@pytest.fixture
async def dask_scheduler_service(
    simcore_services_ready: None, monkeypatch: pytest.MonkeyPatch
) -> str:
    # the dask scheduler has a UI for the dashboard and a secondary port for the API
    # simcore_services fixture already ensure the dask-scheduler is up and running
    dask_scheduler_api_port = get_service_published_port(
        "dask-scheduler", target_ports=[8786]
    )
    # override the port
    monkeypatch.setenv("DASK_SCHEDULER_PORT", f"{dask_scheduler_api_port}")
    url = AnyUrl.build(
        scheme="tls", host=get_localhost_ip(), port=int(dask_scheduler_api_port)
    )
    return f"{url}"


@pytest.fixture
def dask_sidecar_dir(osparc_simcore_services_dir: Path) -> Path:
    path = osparc_simcore_services_dir / "dask-sidecar"
    assert path.exists()
    return path


@pytest.fixture
def dask_backend_tls_certificates_dir(dask_sidecar_dir: Path) -> Path:
    path = dask_sidecar_dir / ".dask-certificates"
    assert path.exists()
    return path


@dataclass(frozen=True, slots=True, kw_only=True)
class _TLSCertificates:
    tls_ca_file: Path
    tls_cert_file: Path
    tls_key_file: Path


@pytest.fixture
def dask_backend_tls_certificates(
    dask_backend_tls_certificates_dir,
) -> _TLSCertificates:
    certs = _TLSCertificates(
        tls_ca_file=dask_backend_tls_certificates_dir / "dask-cert.pem",
        tls_cert_file=dask_backend_tls_certificates_dir / "dask-cert.pem",
        tls_key_file=dask_backend_tls_certificates_dir / "dask-key.pem",
    )
    assert certs.tls_ca_file.exists()
    assert certs.tls_cert_file.exists()
    assert certs.tls_key_file.exists()
    return certs


@pytest.fixture
def dask_scheduler_auth(
    dask_backend_tls_certificates: _TLSCertificates,
) -> InternalClusterAuthentication:
    return TLSAuthentication(
        tls_ca_file=dask_backend_tls_certificates.tls_ca_file,
        tls_client_cert=dask_backend_tls_certificates.tls_cert_file,
        tls_client_key=dask_backend_tls_certificates.tls_key_file,
    )


@pytest.fixture
def dask_client_security(
    dask_backend_tls_certificates: _TLSCertificates,
) -> distributed.Security:
    return distributed.Security(
        tls_ca_file=f"{dask_backend_tls_certificates.tls_ca_file}",
        tls_client_cert=f"{dask_backend_tls_certificates.tls_cert_file}",
        tls_client_key=f"{dask_backend_tls_certificates.tls_key_file}",
        require_encryption=True,
    )


@pytest.fixture
def dask_client(
    dask_scheduler_service: str, dask_client_security: distributed.Security
) -> Iterator[Client]:
    client = Client(dask_scheduler_service, security=dask_client_security)
    yield client
    client.close()


@pytest.fixture
def dask_sidecar_service(dask_client: Client) -> None:
    dask_client.wait_for_workers(n_workers=1, timeout=30)
