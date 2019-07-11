# [vscode] configuration folder

Recommended workspace settings for [vscode]. **PLEASE** keep this file clean and entries sorted alphabetically (at least first entry).

Duplicate and rename this folder as ``.vscode``.

``settings.json`` contains the predefined settings for the code editor and other recommended extensions. Please don't change the ones regarding code formatting.

The recommended extensions are:
- Docker extension
- Python extension
- vscode-icons extension (cool icons on the file browser)
- Babel JavaScript
- ESLint JavaScript linter

Install those with the following commands:
```
code --install-extension PeterJausovec.vscode-docker
code --install-extension robertohuertasm.vscode-icons
code --install-extension ms-python.python
code --install-extension mgmcdermott.vscode-language-babel
code --install-extension dbaeumer.vscode-eslint
```
If VSCode was already running, you need to reload to see them installed. For that you can hit ``Ctrl+Shift+P`` and execute the command ``Reload Window``.

To configure ESLint to use the project linter settings, you will have to first install npm (for that you will need NodeJs as well) and then issue the following commands:
```
npm install eslint
# Qooxdoo rules
npm install eslint-config-qx
npm install babel-eslint
```

## Workarounds

 - [vscode] interactive testing does not work if pytest config fails. Moving ``pytest.ini`` in the root and add setting searching paths for testing folders solves the problem

[vscode]:(https://code.visualstudio.com/)


## Debugging

### PTVSD Remote Debugging using VS code

Your service needs to be started accordingly. See for example ``services/storage/docker/boot.sh``. For an example ``launch.json`` configuration, check the template in this folder. Add environment variables and published ports in the docker-compose.devel.yml file. For example

```yml
#--------------------------------------------------------------------
  storage:
    image: services_storage:dev
    build:
      target: development
    volumes:
      - ./storage:/devel/services/storage
      - ../packages:/devel/packages
    environment:
      - SC_BOOT_MODE=debug-ptvsd
    ports:
      - "3000:3000"
    stdin_open: true
    tty: true
```

This can also be done via Portainer in a running swarm. For production images, make sure to verify the location of the installed packages.

**Usage**: Run the debug config ``Python: Remote Attach storage`` and set some breakpoints.
