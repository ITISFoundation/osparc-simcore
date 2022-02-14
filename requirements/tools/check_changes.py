import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from packaging.version import Version

BEFORE_PATTERN = re.compile(r"^-([\w-]+)==([0-9\.post]+)")
AFTER_PATTERN = re.compile(r"^\+([\w-]+)==([0-9\.post]+)")


def dump_changes(filename: Path):
    subprocess.run(f"git --no-pager diff > {filename}", shell=True, check=True)


def tag_upgrade(from_version: Version, to_version: Version):
    assert from_version < to_version
    if from_version.major < to_version.major:
        return "**MAJOR**"
    if from_version.minor < to_version.minor:
        return "*minor*"
    return ""


def parse_changes(filename: Path):
    changes = []
    before = defaultdict(list)
    after = defaultdict(list)
    with filename.open() as fh:
        for line in fh:
            if match := BEFORE_PATTERN.match(line):
                name, version = match.groups()
                before[name].append(Version(version))
                changes.append(name)
            elif match := AFTER_PATTERN.match(line):
                name, version = match.groups()
                after[name].append(Version(version))
    return before, after, Counter(changes)


def main():

    filepath = Path("changes.ignore.keep.log")
    if not filepath.exists():
        dump_changes(filepath)

    before, after, counts = parse_changes(filepath)

    # format
    print("Stats")
    print("- #packages before:", len(before))
    print("- #packages after :", len(after))
    print()

    COLUMNS = ["#", "name", "before", "after", "upgrade", " count"]

    print("|" + "|".join(COLUMNS) + "|")
    print("|" + "|".join(["-" * len(c) for c in COLUMNS]) + "|")
    for i, name in enumerate(sorted(before.keys()), start=1):
        # TODO: where are these libraries?
        # TODO: are they first dependencies?
        # TODO: if major, get link to release notes
        from_versions = set(str(v) for v in before[name])
        to_versions = set(str(v) for v in after[name])

        print(
            "|",
            f"{i:2d}",
            "|",
            f"{name:25s}",
            "|",
            f'{", ".join(from_versions):15s}',
            "|",
            f'{",".join(to_versions) if to_versions else "removed":10s}',
            "|",
            # how big the version change is
            f"{tag_upgrade(sorted(set(before[name]))[-1], sorted(set(after[name]))[-1]):10s}"
            if to_versions
            else "",
            "|",
            counts[name],
            "|",
        )


if __name__ == "__main__":
    main()
