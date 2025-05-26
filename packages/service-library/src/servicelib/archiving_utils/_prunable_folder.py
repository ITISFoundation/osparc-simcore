import logging
from contextlib import suppress
from pathlib import Path

_logger = logging.getLogger(__name__)


def is_leaf_path(p: Path) -> bool:
    """Tests whether a path corresponds to a file or empty folder, i.e.
    some leaf item in a file-system tree structure
    """
    return p.is_file() or (p.is_dir() and not any(p.glob("*")))


class PrunableFolder:
    """
    Use in conjunction with unarchive on the dest_dir to achieve
    an update of a folder content without deleting updated files

    folder = PrunableFolder(target_dir)

    unarchived = await archive_dir(destination=target_dir, ... )

    folder.prune(exclude=unarchived)

    """

    def __init__(self, folder: Path):
        self.basedir = folder
        self.before_relpaths: set = set()
        self.capture()

    def capture(self) -> None:
        # captures leaf paths in folder at this moment
        self.before_relpaths = {
            p.relative_to(self.basedir)
            for p in self.basedir.rglob("*")
            if is_leaf_path(p)
        }

    def prune(self, exclude: set[Path]) -> None:
        """
        Deletes all paths in folder skipping the exclude set
        """

        after_relpaths = {p.relative_to(self.basedir) for p in exclude}
        to_delete = self.before_relpaths.difference(after_relpaths)

        for p in to_delete:
            path = self.basedir / p
            assert path.exists()  # nosec

            if path.is_file():
                path.unlink()
            elif path.is_dir():
                # prevents deleting non-empty folders
                with suppress(OSError):
                    path.rmdir()

        # second pass to delete empty folders
        # after deleting files, some folders might have been left empty
        for p in self.basedir.rglob("*"):
            if p.is_dir() and p not in exclude and not any(p.glob("*")):
                p.rmdir()
