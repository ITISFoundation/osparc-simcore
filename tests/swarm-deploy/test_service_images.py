import subprocess
import os



def test_ujson_installation_in_director():
    registry = os.environ.get("DOCKER_REGISTRY", "local")
    tag = os.environ.get("DOCKER_IMAGE_TAG", "production")

    assert subprocess.run(
        f'docker run -t --rm {registry}/director:{tag} python -c "import ujson; print(ujson.__version__)"',
        shell=True,
        check=True,
    )
