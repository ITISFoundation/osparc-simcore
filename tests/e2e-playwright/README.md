# e2e with playwright

## Usage

### Auto generate new test

```cmd
playwright codegen sim4life.io
```

### Run test locally with headed mode

```cmd
pytest -s tests/sim4life.py --headed --browser chromium --product-billable  --product-url https://sim4life.io/ --user-name YOUR_USERNAME --password YOUR_PASSWORD --service-key sim4life-8-0-0-dy
```

### Check test results output

```cmd
playwright show-trace test-results/tests-sim4life-py-test-billable-sim4life-chromium/trace.zip
```

### Run debug mode

```cmd
PWDEBUG=1 pytest -s tests/sim4life.py
```

### Run test in different browsers

```cmd
pytest -s tests/sim4life.py --tracing on --html=report.html --browser chromium --browser firefox
```

### or in chrome/ms-edge

```cmd
pytest -s tests/sim4life.py --tracing on --html=report.html --browser-channel chrome
```

## Portal suite

`tests/portal` is the Playwright equivalent of the legacy Puppeteer scripts in `tests/e2e/portal`,
`tests/e2e/portal-files` and `tests/e2e/publications`. Unlike the other suites, it opens a
**public/portal study without logging in** (via the `open_study_link` fixture), so it doesn't need
`--product-url`, `--user-name` or `--password`.

### Run a portal test locally

```cmd
pytest -s tests/portal/test_2d_plot.py --headed --browser chromium \
  --anonymous-study-url https://<url_prefix><template_uuid> \
  --service-start-timeout 60000
```

Computational-pipeline portal tests (`test_cc_human.py`, `test_cc_rabbit.py`, `test_opencor.py`,
`test_kember.py`) wait for a pipeline run instead of a dynamic service, so they use
`--run-pipeline-timeout` (default 180000ms) instead of `--service-start-timeout`.

`tests/portal/test_vtk_file.py` (port of the legacy `tests/e2e/portal-files/VTK_file.js`) resolves
its study URL from a viewer/file instead, so it takes different options:

```cmd
pytest -s tests/portal/test_vtk_file.py --headed --browser chromium \
  --viewer-url-prefix https://<osparc-host> \
  --download-link https://<file-url> \
  --file-size <bytes>
```

### Or interactively, with cached settings

```cmd
make test-portal-anywhere                          # uses the cached test file
make test-portal-anywhere TEST=test_2d_plot.py     # overrides it for this run
```

`make test-portal-anywhere` always runs a single test inside `tests/portal` — running the whole
suite at once isn't supported, since each test targets a different public template study and there
is only one `--anonymous-study-url`. The first time it runs, it asks which test file to run (e.g.
`test_2d_plot.py`, required) and caches the answer alongside the other settings in
`.e2e-playwright-portal-env.txt`. If you enter `test_vtk_file.py`, it asks for the
`--viewer-url-prefix`/`--download-link`/`--file-size` options instead of `--anonymous-study-url`.
Use `TEST=...` (just the filename, not the full path) to override the cached value for a single
run — note this only changes which test runs, not which options were cached, so switching between
`test_vtk_file.py` and the rest requires `make clean` to be re-prompted with the right questions.

Studies protected by HTTP basic auth can be reached with `--basic-auth-user`/`--basic-auth-password`.

## e2e CI

- [e2e-ci repository](https://git.speag.com/oSparc/e2e-backend): repo and dashboard for daily CI runs
