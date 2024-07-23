### Auto generate new test
`playwright codegen sim4life.io`

### Run test locally with headed mode
```
pytest -s tests/sim4life.py --headed --browser chromium --product-billable  --product-url https://sim4life.io/ --user-name YOUR_USERNAME --password YOUR_PASSWORD --service-key simcore/services/dynamic/sim4life-8-0-0-dy --service-test-id studyBrowserListItem_simcore/services/dynamic/sim4life-8-0-0-dy
```

### Check test results output
`playwright show-trace test-results/tests-sim4life-py-test-billable-sim4life-chromium/trace.zip`

### Run debug mode
`PWDEBUG=1 pytest -s tests/sim4life.py`

### Run test in different browsers
`pytest -s tests/sim4life.py --tracing on --html=report.html --browser chromium --browser firefox`

### Runs in CI
  - https://git.speag.com/oSparc/e2e-backend
