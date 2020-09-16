from pathlib import Path
import sys
from typing import Dict
import json

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def get_fake_data_dir() -> str:
    return (current_dir / ".." / "data").resolve()


def get_fake_project() -> Dict:
    with (get_fake_data_dir() / "fake-project.json").open() as fp:
        return json.load(fp)
