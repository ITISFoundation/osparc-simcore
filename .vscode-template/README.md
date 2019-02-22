# [vscode] configuration folder

Recommended workspace settings for [vscode]. **PLEASE** keep this file clean and entries sorted alphabetically (at least first entry).

Duplicate and rename this folder as ``.vscode``.

``settings.json`` contains the predefined settings for the code editor and other recommended extensions. Please don't change the ones regarding code formatting.

The recommended extensions are:
- Docker extension
- Python extension
- vscode-icons extension (cool icons on the file browser)

Install those with the following commands:
```
code --install-extension PeterJausovec.vscode-docker
code --install-extension robertohuertasm.vscode-icons
code --install-extension ms-python.python
code --install-extension mgmcdermott.vscode-language-babel
```
If VSCode was already running, you need to reload to see them installed. For that you can hit ``Ctrl+Shift+P`` and execute the command ``Reload Window``.

## Workarounds

 - [vscode] interactive testing does not work if pytest config fails. Moving ``pytest.ini`` in the root and add setting searching paths for testing folders solves the problem

[vscode]:(https://code.visualstudio.com/)
