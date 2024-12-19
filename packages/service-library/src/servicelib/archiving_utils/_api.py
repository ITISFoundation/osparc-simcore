# used to switch between implementations

# from ._interface_zipfile import archive_dir, unarchive_dir
from ._interface_7zip import archive_dir, unarchive_dir

__all__: tuple[str, ...] = (
    "archive_dir",
    "unarchive_dir",
)

# nopycln: file
