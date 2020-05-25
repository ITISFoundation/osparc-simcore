## To run the tests locally
```bash
npm install
npm test
```
## To debug the tests locally with VSCode
Add the following configuration to your local ``launch.json``:
```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug e2e tests",
  "runtimeArgs": [
    "--inspect-brk",
    "${workspaceRoot}/tests/e2e/node_modules/.bin/jest",
    "--runInBand",
    "--colors"
  ],
  "cwd": "${workspaceFolder}/tests/e2e",
  "restart": true,
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen",
  "port": 9229
}
```
Now you can run the tests by clicking on the Play button, using that configuration. It should allow you to insert breakpoints and inspect variables.
