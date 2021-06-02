import tempfile
from pathlib import Path

from simcore_service_sidecar.utils import touch_tmpfile


def test_touch_tmpfile():

    try:
        some_file = touch_tmpfile(extension=".foo")
        assert some_file.exists()
        assert some_file.suffix == ".foo"

        assert Path(tempfile.gettempdir()) == some_file.parent

        some_file.write_text("I can write")
        assert some_file.read_text() == "I can write"
    finally:
        some_file.unlink()
