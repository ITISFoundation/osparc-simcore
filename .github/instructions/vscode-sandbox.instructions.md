---
applyTo: '.vscode/**'
---

## VS Code Terminal Sandbox

This workspace sandboxes AI terminal commands. The active rules are in `.vscode/settings.json` (generated from `settings.template.json`; users may customize it). Settings keys are prefixed with `chat.tools.terminal.sandbox.*`.

### Working in the sandbox

- **Read `.vscode/settings.json`** to learn the current `denyRead`, `denyWrite`, and `allowWrite` lists before running commands that touch paths outside the workspace. Check the OS-appropriate section (`linuxFileSystem` or `macFileSystem`).
- **Write only inside the workspace.** Use relative paths or `$PWD`. Use `$TMPDIR` for temp files (not `/tmp`).
- **On "Operation not permitted" / "Permission denied"**: the sandbox blocked it. Check the deny lists, find an alternative (e.g. env vars instead of credential files, `git config --local --list` instead of `~/.gitconfig`), or ask the developer to run it manually.
- **Never bypass** the sandbox via `sudo`, symlinks, or other workarounds.

### Editing sandbox settings

- Never remove entries from `denyRead` / `denyWrite`. Never disable the sandbox. Never widen `allowWrite` beyond `.`.
- Adding new deny paths is encouraged. Keep `linuxFileSystem` and `macFileSystem` in sync.
- `chat.autopilot.enabled` must remain `false`.
