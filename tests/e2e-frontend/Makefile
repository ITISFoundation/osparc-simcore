install-dev:
	npm install

.PHONY: run-tests
run-tests: install-dev ## run tests headless
	npx playwright test

.PHONY: run-tests-headed
run-tests-headed: install-dev ## run tests headed (you can see what's going on)
	npx playwright test --headed

.PHONY: run-tests-ui
run-tests-ui: install-dev ## run tests headed with an assistance GUI
	npx playwright test --ui
