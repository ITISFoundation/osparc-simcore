import sys
from pathlib import Path
from typing import List


def get_exported_projects() -> List[Path]:
    # These files are generated from the front-end
    # when the formatter be finished
    current_dir = (
        Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    )
    data_dir = current_dir.parent.parent / "data"
    assert data_dir.exists(), "expected folder under tests/data"
    exporter_dir = data_dir / "exporter"
    assert exporter_dir.exists()
    exported_files = [x for x in exporter_dir.glob("*.osparc")]
    assert exported_files, "expected *.osparc files, none found"
    return exported_files
