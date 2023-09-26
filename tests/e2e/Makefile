include ../../scripts/common.Makefile

SIMCORE_DOT_ENV = $(abspath $(CURDIR)/../../.env)


# UTILS ############
define _build_simcore_images
# build simcore images using the selected flavor
$(if $(findstring -ci,$@),$(MAKE_C) $(REPO_BASE_DIR) pull-version tag-local ||,) $(MAKE_C) $(REPO_BASE_DIR) build$(if $(findstring -dev,$@),-devel,)
$(MAKE_C) $(REPO_BASE_DIR) info-images
endef

define _up_simcore
# set some parameters to allow for e2e to run
echo LOGIN_REGISTRATION_INVITATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
echo LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
echo DEFAULT_MAX_NANO_CPUS=1000000000 >> $(SIMCORE_DOT_ENV)
echo DEFAULT_MAX_MEMORY=134217728 >> $(SIMCORE_DOT_ENV)
echo SIDECAR_FORCE_CPU_NODE=1 >> $(SIMCORE_DOT_ENV)
$(MAKE_C) $(REPO_BASE_DIR) up-prod ops_ci=1
endef

define _setup_test_environment
# setup the python environment
$(MAKE_C) $(REPO_BASE_DIR) devenv
$(VENV_DIR)/bin/pip install -r requirements/requirements.txt
# setup node environment for puppeteer
npm install
endef

define _transfer-images-to-registry
# pushing sleeper image
@docker pull itisfoundation/sleeper:1.0.0
@docker tag itisfoundation/sleeper:1.0.0 registry:5000/simcore/services/comp/itis/sleeper:1.0.0
@docker push registry:5000/simcore/services/comp/itis/sleeper:1.0.0
# completed transfer of images
@curl -s registry:5000/v2/_catalog | jq '.repositories'
@curl -s http://registry:5000/v2/simcore/services/comp/itis/sleeper/tags/list?n=50 | jq '.'
endef

define _transfer-jupyter-from-master-to-registry
# smash image
@docker pull registry.osparc-master.speag.com/simcore/services/dynamic/jupyter-smash:3.0.7
@docker tag registry.osparc-master.speag.com/simcore/services/dynamic/jupyter-smash:3.0.7 registry:5000/simcore/services/dynamic/jupyter-smash:3.0.7
@docker push registry:5000/simcore/services/dynamic/jupyter-smash:3.0.7
# completed transfer of images
@curl -s registry:5000/v2/_catalog | jq '.repositories'
@curl -s http://registry:5000/v2/simcore/services/dynamic/jupyter-smash/tags/list?n=50 | jq '.'
endef

NUMBERS = 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
define _register-20-users
$(foreach var,$(NUMBERS),\
	curl -d '{"email":"test$(var)@test.com","password":"testpassword123","confirm":"testpassword123","invitation":""}' -H "Content-Type: application/json" -X POST http://localhost:9081/v0/auth/register \
;)
endef


# Below feels a bit like magic I am not sure why the thing awaits for the scirpts to finish
DEV_MACHINE_IP = "10.43.103.168"
define _test-jupyters
echo $(shell python -c 'import os ;\
[os.system("node --trace-warnings tutorials/jupyterlabs.js http://${DEV_MACHINE_IP}.nip.io:9081 test%s@test.com testpassword123 60000 &" % x) for x in range(1, 21)]
')
echo "finished parallel run"
endef

define _inject-templates-in-db
# inject the sleepers template
@docker cp tutorials/sleepers_project_template_sql.csv $$(docker ps -q --filter="name=postgres"):/template_projects_sleepers_project_template_sql.csv
# template is copied into the postgres container and then injected
@docker exec $$(docker ps -q --filter="name=postgres") psql --user scu --dbname simcoredb --command "\copy projects from '/template_projects_sleepers_project_template_sql.csv' csv header;"
endef

# SETUP ##################

.PHONY: install-ci-no-build install-ci install-prod clean-up

install-ci-no-build:
	@$(MAKE_C) $(REPO_BASE_DIR) local-registry
	@$(_up_simcore)
	@$(_setup_test_environment)
	@$(VENV_DIR)/bin/python utils/wait_for_services.py
	@$(_transfer-images-to-registry)
	@$(_inject-templates-in-db)

install-ci install-prod: ## install e2e testing framework and start simcore/registry
	@$(_build_simcore_images)
	@$(MAKE_C) $(REPO_BASE_DIR) local-registry
	@$(_up_simcore)
	@$(_setup_test_environment)
	@$(VENV_DIR)/bin/python utils/wait_for_services.py
	@$(_transfer-images-to-registry)
	@$(_inject-templates-in-db)

clean-up: ## remove everything
	# switch simcore stack down
	@$(MAKE_C) $(REPO_BASE_DIR) down
	# leave docker swarm
	@$(MAKE_C) $(REPO_BASE_DIR) leave
	# remove local registry
	@$(MAKE_C) $(REPO_BASE_DIR) rm-registry




.PHONY: test
test: ## test the platform
	# tests
	npm test
	# tests whether tutorial run
	npm run tutorials http://127.0.0.1:9081


.PHONY: dev-prepare-jupyters
dev-prepare-jupyters: ## pull images and create users
	@$(_transfer-jupyter-from-master-to-registry)
	@$(_register-20-users)
	@echo "NOTE: Below should be automated in the future"
	@echo "- remember to give permission to the service"
	@echo "- remmeber to import the JupyterLabs template in the deployment"


.PHONY: dev-test-jupyters
dev-test-jupyters: ## run the parallel jupyter tests
	@$(_test-jupyters)
