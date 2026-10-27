from pathlib import Path

import yaml


def _image_references(compose_path: Path) -> list[str]:
    specs = yaml.safe_load(compose_path.read_text())
    return [service["image"] for service in (specs or {}).get("services", {}).values() if service.get("image")]


def _repository(image: str) -> str:
    """The image reference without its tag and digest, e.g. `valkey/valkey` in
    `valkey/valkey:7.2.14@sha256:...`"""
    reference = image.split("@", 1)[0]
    name = reference.rsplit("/", 1)[-1]
    return reference[: reference.rindex(":")] if ":" in name else reference


def test_docker_composes_service_versions(osparc_simcore_root_dir: Path):
    # A test docker-compose fixture may run extra images (adminer, redis-commander, ...) but must pin
    # the exact same reference as the main stack for every image it shares with it: a fixture drifting
    # to another tag or digest silently exercises a version CI and the product never run, e.g. the
    # partial Docker-digest update of PR #9915 that moved the main compose to a new valkey digest and
    # left the test fixtures on the old one.
    main_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    main_images: dict[str, set[str]] = {}
    for image in _image_references(main_compose_path):
        if "${" not in image:  # templated references to the services' own builds have no pin to match
            main_images.setdefault(_repository(image), set()).add(image)

    for compose_file in sorted((osparc_simcore_root_dir / "services").glob("**/tests/**/docker-compose*.yml")):
        for image in _image_references(compose_file):
            if "${" in image:
                continue
            repository = _repository(image)
            if repository in main_images:
                assert image in main_images[repository], (
                    f"{compose_file.relative_to(osparc_simcore_root_dir)} pins {image},"
                    f" main stack pins {sorted(main_images[repository])}"
                )
