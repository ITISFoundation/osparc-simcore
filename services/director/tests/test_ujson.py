#
# Tests instalation issues related to ujson inside or outside the container
#  https://github.com/kohlschutter/junixsocket/issues/33
#
import subprocess
import sys
import os
from pathlib import Path

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def test_ujson_installation():
    # pylint: disable=c-extension-no-member
    import ujson

    assert ujson.__version__

    with open(current_dir / "fixtures/dummy_service_description-v1.json") as fh:
        obj = ujson.load(fh)
        assert ujson.loads(ujson.dumps(obj)) == obj


def test_docker_installation():
    registry = os.environ.get("DOCKER_REGISTRY", "local")
    tag = os.environ.get("DOCKER_IMAGE_TAG", "production")

    assert subprocess.run(
        f'docker run -t --rm {registry}/director:{tag} python -c "import ujson; print(ujson.__version__)"',
        shell=True,
        check=True,
    )
