Auto generate new test
`playwright codegen sim4life.py`

Run test locally with headed mode
`pytest -s test sim4life.py --tracing on --headed `

Check test results output
`playwright show-trace test-results/tests-sim4life-py-test-billable-sim4life-chromium/trace.zip`

Run debug mode
`PWDEBUG=1 pytest --s tests/sim4life.py`

Run test in different browsers
`pytest -s tests/sim4life.py --tracing on --html=report.html --browser chromium --browser firefox`
