## To run the tests locally
```bash
cd tests/e2e
npm install
npm test
# or
npm run tutorials http://127.0.0.1:9081 --demo
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
## To run the tutorials
```bash
cd tests/e2e
node tutorials/<tutorial>.js [<user> <password>]
```
