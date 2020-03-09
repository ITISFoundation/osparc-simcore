#
# https://github.com/kohlschutter/junixsocket/issues/33
#
import sys
from pathlib import Path

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

def test_ujson_installation():
    import ujson
    assert ujson.__version__

    with open( current_dir / "fixtures/dummy_service_description-v1.json" ) as fh:
        obj = ujson.load(fh)
        assert ujson.loads(ujson.dumps(obj)) == obj
