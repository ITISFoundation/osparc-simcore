# end-to-end (e2e) testing


Presentation "[Understanding e2e testing](https://docs.google.com/presentation/d/1Kc2kz1e6Fl3XNDGXfPx_Aurqx29edGuke4rnIfHr5bI/edit?usp=sharing)" by @odeimaiz on Dec 2, 2020


**WARNING**: Be aware that running these tests in your host might risk changing some
configuration.

## To run the tests locally

Setting up the test

```bash
/bin/bash ci/github/system-testing/e2e.bash clean_up
docker volume prune
/bin/bash ci/github/system-testing/e2e.bash install
```

Run the test
```bash
/bin/bash ci/github/system-testing/e2e.bash test
```
To run a single toutorial
```
cd tests/e2e
npm test
node tutorials/jupyterlabs.js http://127.0.0.1:9081
```

Trying to cleanup
```bash
/bin/bash ci/github/system-testing/e2e.bash clean_up
```

## To debug the tests locally with VSCode
Add the following configuration to your local ``launch.json``:
```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug tutorials/{FILE}",
  "program": "${workspaceFolder}/tests/e2e/tutorials/${fileBasename}",
  "args": [
    "http://127.0.0.1:9081"
  ],
  "cwd": "${workspaceFolder}/tests/e2e",
  "stopOnEntry": false,
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen"
}
```
Now you can run the tests by clicking on the Play button, using that configuration. It should allow you to insert breakpoints and inspect variables.


## Run end-to-end

```cmd
cd tests/e2e
npm install --save
node tutorials/{{test.js}} {{deployment}} (--user {{user}}) (--pass {{password}}) (--demo)
node tutorials/sleepers.js https://osparc-master.speag.com/ --user user@domain --pass mypass --demo
```
## Run portal-to-end

```cmd
cd tests/e2e
npm install --save
node portal/{{test.js}} {{deployment}}/study/ {{published_template_uuid}}
# example
node portal/2D_Plot.js https://osparc-master.speag.com/study/ 003aaf4a-524a-11ea-b061-02420a00070b
```
