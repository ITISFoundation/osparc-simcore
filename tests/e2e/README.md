# end-to-end (e2e) testing


Presentation "[Understanding e2e testing](https://docs.google.com/presentation/d/1Kc2kz1e6Fl3XNDGXfPx_Aurqx29edGuke4rnIfHr5bI/edit?usp=sharing)" by @odeimaiz on Dec 2, 2020


**WARNING**: Be aware that running these tests in your host might risk changing some
configuration.

## To run the tests locally

#### Dependencies

```bash
/bin/bash ci/github/system-testing/e2e.bash clean_up
docker volume prune
/bin/bash ci/github/system-testing/e2e.bash install
```

#### To run a single tutorial in the terminal
```
cd tests/e2e
node tutorials/sleepers.js http://127.0.0.1:9081
```

#### To run the same with the debugger attached in VScode:
- open `tests/e2e/tutorials/sleepers.js` in VSCode
- go to `Run and Debug`
- from the dropdown select `Debug tutorials/FILE`
- press Play button

**NOTE:** if breakpoints were added they should become active now.

#### Cleanup after you are done
```bash
/bin/bash ci/github/system-testing/e2e.bash clean_up
```

---

## Run against a different deployment

Add the following to your `.vscode/launch.json` file

```js
 {
  "type": "node",
  "request": "launch",
  "name": "Debug rclone_small.js @ staging.osparc.io",
  "program": "${workspaceFolder}/tests/e2e/tutorials/${fileBasename}",
  "args": [
    "https://DEPLYMENTADDRESS",
    "--user",
    "USER@E.MAIL",
    "--pass",
    "USER_PASSWORD",
    "--demo",
    "--start_timeout",
    "200000"
  ],
  "cwd": "${workspaceFolder}/tests/e2e",
  "stopOnEntry": false,
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen"
}
```

----

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
