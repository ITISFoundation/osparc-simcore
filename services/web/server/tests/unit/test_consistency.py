from pathlib import Path

import yaml


def test_docker_composes_service_versions(osparc_simcore_root_dir: Path, here: Path):
    # look for main docker-compose file
    main_docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    main_docker_compose_specs = yaml.safe_load(main_docker_compose_path.open())
    main_services_image_names = [service["image"] for _service_name, service in main_docker_compose_specs["services"].items()]

    # look for other docker-compose files in test folders
    for compose_file in here.glob('**/docker-compose.yml'):
        compose_specs = yaml.safe_load(compose_file.open())
        service_image_names = [service["image"] for _service_name, service in compose_specs["services"].items()]

        assert all(elem in main_services_image_names for elem in service_image_names)
