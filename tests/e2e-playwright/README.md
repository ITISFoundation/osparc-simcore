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

## e2e CI

- [e2e-ci repository](https://git.speag.com/oSparc/e2e-backend): repo and dashboard for daily CI runs
