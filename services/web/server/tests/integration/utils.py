import json
import sys
from pathlib import Path
from typing import Dict

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def get_fake_data_dir() -> Path:
    return (current_dir / ".." / "data").resolve()


def get_fake_project() -> Dict:
    with (get_fake_data_dir() / "fake-project.json").open() as fp:
        return json.load(fp)
