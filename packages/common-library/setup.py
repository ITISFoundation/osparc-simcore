from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

_LOCALE_DIR = Path(__file__).resolve().parent / "src" / "common_library" / "locale"


def _compile_locale(locale_dir: Path) -> None:
    """Compile all .po files to .mo in-place using polib (no system msgfmt required)."""
    if not locale_dir.is_dir():
        return
    import polib  # available as a build-system requirement (pyproject.toml)  # noqa: PLC0415

    for po_path in locale_dir.glob("*/LC_MESSAGES/messages.po"):
        polib.pofile(str(po_path)).save_as_mofile(str(po_path.with_suffix(".mo")))


class BuildPyRunner(_build_py):
    """Extends build_py to compile locale .po files to .mo before packaging."""

    def run(self) -> None:
        _compile_locale(_LOCALE_DIR)
        super().run()


setup(cmdclass={"build_py": BuildPyRunner})
