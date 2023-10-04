from simcore_service_clusters_keeper._meta import PACKAGE_DATA_FOLDER


def test_access_to_docker_compose_yml_file():
    assert f"{PACKAGE_DATA_FOLDER}".endswith("data")
    assert (PACKAGE_DATA_FOLDER / "docker-compose.yml").exists()
