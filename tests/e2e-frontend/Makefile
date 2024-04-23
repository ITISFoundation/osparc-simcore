.PHONY: install
npm install --with-deps
npx playwright install
sudo npx playwright install-deps

run-tests: ## run tests headless
npx playwright test

run-tests-headed:  ## run tests headed (you can see what's going on)
npx playwright test --headed

run-tests-ui:  ## run tests headed with an assistance GUI
npx playwright test --ui
