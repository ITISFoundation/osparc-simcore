from pathlib import Path

TRANSLATION_DIR = Path(__file__).parent.joinpath("..", "source", "translation").resolve()
NO_LONGER_USED_MARKER = "#. NO LONGER USED"
HEADER_MSGID = 'msgid ""'


def _remove_no_longer_used_entries(po_path: Path) -> int:
    blocks = po_path.read_text(encoding="utf-8").strip("\n").split("\n\n")
    kept: list[str] = []
    removed = 0
    for block in blocks:
        lines = block.split("\n")
        if HEADER_MSGID in lines:
            # the gettext header is never dropped; just clean the spurious marker
            kept.append("\n".join(line for line in lines if line != NO_LONGER_USED_MARKER))
        elif NO_LONGER_USED_MARKER in lines:
            # entry no longer present in the source code
            removed += 1
        else:
            kept.append(block)
    po_path.write_text("\n\n".join(kept) + "\n", encoding="utf-8")
    return removed


def remove_no_longer_used_entries():
    for po_path in sorted(TRANSLATION_DIR.glob("*.po")):
        removed = _remove_no_longer_used_entries(po_path)
        print(f"Removed {removed} 'NO LONGER USED' entries from {po_path.name}")  # noqa: T201


if __name__ == "__main__":
    remove_no_longer_used_entries()
