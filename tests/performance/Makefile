#
# Targets for DEVELOPMENT for performance test web-api
#
include ../../scripts/common.Makefile

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install
install-dev: _check_venv_active  ## installs dependencies
	# installing requirements
	pip-sync requirements/dev.txt


.PHONY: start
start: _check_venv_active  ## starts locust, a scriptable and scalable performance testing tool
	# Open http://localhost:8089/
	locust --locustfile locustfile.py --host http://127.0.0.1:9081  --users 3 --spawn-rate 1


.PHONY: list
list: _check_venv_active
	locust --list
