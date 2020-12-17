include ../../scripts/common.Makefile

SIMCORE_DOT_ENV = $(abspath $(CURDIR)/../../.env)


# UTILS ############
define _build_simcore_images
# build simcore images using the selected flavor
$(if $(findstring -ci,$@),$(MAKE_C) $(REPO_BASE_DIR) pull-version tag-local ||,) $(MAKE_C) $(REPO_BASE_DIR) build$(if $(findstring -dev,$@),-devel,)-x
$(MAKE_C) $(REPO_BASE_DIR) info-images
endef

define _up_simcore
# set some parameters to allow for e2e to run
echo WEBSERVER_LOGIN_REGISTRATION_INVITATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
echo WEBSERVER_LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
echo SERVICES_MAX_NANO_CPUS=2000000000 >> $(SIMCORE_DOT_ENV)
echo SIDECAR_FORCE_CPU_NODE=1 >> $(SIMCORE_DOT_ENV)
$(MAKE_C) $(REPO_BASE_DIR) up-prod
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


define _inject-templates-in-db
# inject the sleepers template
@docker cp tutorials/sleepers_project_template_sql.csv $$(docker ps -q --filter="name=postgres"):/template_projects_sleepers_project_template_sql.csv
# template is copied into the postgres container and then injected
@docker exec $$(docker ps -q --filter="name=postgres") psql --user scu --dbname simcoredb --command "\copy projects from '/template_projects_sleepers_project_template_sql.csv' csv header;"
endef

# SETUP ##################

.PHONY: install-ci install-prod clean-up
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



# TEST ###############
.PHONY: test
test: ## test the platform
	# tests
	npm test
	# tests whether tutorial run
	npm run tutorials http://127.0.0.1:9081
