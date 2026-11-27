import shutil
from pathlib import Path


def make_path_write_executable(path: Path, content: str) -> None:
    """Write an executable script to ``path``"""
    path.write_text(content)
    path.chmod(0o755)


def create_link_to_tool_in_path(bin_dir: Path, tool: str) -> None:
    """Link ``tool`` from the current PATH into ``bin_dir``, so a script run with PATH=bin_dir sees it"""
    tool_path = shutil.which(tool)
    assert tool_path, f"{tool} not found in PATH"
    (bin_dir / tool).symlink_to(tool_path)
