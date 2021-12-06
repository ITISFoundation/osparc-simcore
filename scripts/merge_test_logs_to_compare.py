# This script aids in the comparison of two log files of github action runners.
import sys
from io import StringIO
from pathlib import Path


def clean():
    for fpath in Path().rglob("*"):
        if fpath.suffix == ".txt":
            truncated_lines = [line[9:] for line in fpath.read_text().splitlines()]
            fpath.write_text("\n".join(truncated_lines))


def join(basedir):
    msg = StringIO()
    for fpath in basedir.rglob("*.txt"):
        if "linting" in str(fpath):
            print("", end="\n")
            print("=" * 100, file=msg)
            print(f"{fpath}", file=msg)
            print("-" * 200, file=msg)
            truncated_lines = [line[28:] for line in fpath.read_text().splitlines()]
            print("\n".join(truncated_lines), file=msg)
            print("=" * 100, end="\n" * 2, file=msg)
    return msg.getvalue()


def main(fails_folder, passes_folder):
    for folder in (fails_folder, passes_folder):
        Path(f"{folder.name}.txt").write_text(join(folder))


if __name__ == "__main__":
    """
    Download logs from two failing CI runs
    Save them in two separate folders


    python merge_test_logs_to_compare.py $fails_folder $passes_folder

    """
    main(fails_folder=Path(sys.argv[1]), passes_folder=Path(sys.argv[2]))
