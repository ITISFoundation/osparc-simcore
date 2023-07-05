#
# Targets for DEVELOPMENT of tests/public-api
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

# MAIN ------------------

# Redirections to recipes in the main Makefile
.PHONY: leave build
leave build:
	$(MAKE_C) $(REPO_BASE_DIR) $@


# LOCAL ------------------

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: test-dev
test-dev: ## runs tests with --keep-docker-up, --pdb and --ff
	# WARNING:
	#   - do not forget to build latest changes images
	#   - this test can be affected by existing docker volumes in your host machine
	#
	# running unit tests
	@pytest --keep-docker-up \
	-vv \
	--color=yes \
	--failed-first \
	--durations=10 \
	--asyncio-mode=auto \
	--pdb \
	$(CURDIR)


.PHONY: test-ci
test-ci: ## runs ci tests (i.e. w/o debug tools and with code coverage)
	@pytest \
	-vv \
	--color=yes \
	--durations=10 \
	$(CURDIR)


REPO := ITISFoundation/osparc-simcore-clients
BRANCH := master
WORKFLOW := publish-and-test-python-client

.PHONY: install-latest-python-osparc
install-latest-python-osparc: ## install the latest python osparc package. Pass the env variables "REPO", "BRANCH" and "WORKFLOW" to customize where to grab the client from
	@echo "Using REPO=$(REPO), BRANCH=$(BRANCH), WORKFLOW=$(WORKFLOW)"
	@-rm -rf ./osparc_python_wheels && python -m pip uninstall osparc -y && python -m pip uninstall osparc_client -y
	@run_id=$$(bash $(SCRIPTS_DIR)/gh.bash run list --repo=$(REPO) --branch=$(BRANCH) --workflow=$(WORKFLOW) --limit=1 --json=databaseId --jq=.[].databaseId); \
	[[ -z "$${run_id}" ]] && { echo "Could not find osparc python package" ; exit 1; };\
	echo "run_id for latest build of '$(WORKFLOW)' on '$(BRANCH)' in '$(REPO)': $${run_id}"; \
	bash $(SCRIPTS_DIR)/gh.bash run download $${run_id} --repo=$(REPO) &&\
	osparc_wheel=$$(ls ./osparc_python_wheels/osparc-*.whl) && \
	python -m pip install $${osparc_wheel} --find-links=./osparc_python_wheels/
