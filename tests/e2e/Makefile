include ../../scripts/common.Makefile

SIMCORE_DOT_ENV = $(abspath $(CURDIR)/../../.env)
DOT_ENV_BACKUP = $(SIMCORE_DOT_ENV).bak

$(DOT_ENV_BACKUP): $(SIMCORE_DOT_ENV)
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


_simcore-images:
	@$(MAKE_C) $(REPO_BASE_DIR) pull-version tag-local || $(MAKE_C) ../.. build-x
	@$(MAKE_C) $(REPO_BASE_DIR) info-images

_local-registry:
	@$(MAKE_C) $(REPO_BASE_DIR) local-registry

_simcore-up:
	@echo WEBSERVER_LOGIN_REGISTRATION_INVITATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
	@echo WEBSERVER_LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
	@echo SERVICES_MAX_NANO_CPUS=2000000000 >> $(SIMCORE_DOT_ENV)
	@echo SIDECAR_FORCE_CPU_NODE=1 >> $(SIMCORE_DOT_ENV)
	@$(MAKE_C) $(REPO_BASE_DIR) up-prod

_test_environment:
	@$(MAKE_C) $(REPO_BASE_DIR) devenv
	# install python dependencies
	@$(VENV_DIR)/bin/pip install -r requirements/requirements.txt
	# install node dependencies (puppeteer...)
	@npm install
	# wait for services being ready
	@$(VENV_DIR)/bin/python utils/wait_for_services.py

.PHONY: install
install: _simcore-images _local-registry _simcore-up _test_environment ## install testing framework
	@$(MAKE) _simcore-images
	@$(MAKE) _local-registry
	@$(MAKE) _simcore-up
	@$(MAKE) _test_environment
	@$(MAKE) transfer-images-to-registry
	@$(MAKE) inject-templates-in-db

clean-up: ## remove everything
	@$(MAKE_C) $(REPO_BASE_DIR) down
	@$(MAKE_C) $(REPO_BASE_DIR) leave


registry-up: ## deploys the insecure docker registry in the simcore network
	docker stack deploy -c docker-compose.yml registry

registry-down: ## bring the docker registry down
	docker stack rm registry


.PHONY: wait-for-services
wait-for-services:  _check_venv_active ## wait for simcore services to be up
	@python utils/wait_for_services.py


.PHONY: transfer-images-to-registry
transfer-images-to-registry: ## transfer images to registry
	# pushing sleeper image
	@docker pull itisfoundation/sleeper:1.0.0
	@docker tag itisfoundation/sleeper:1.0.0 registry:5000/simcore/services/comp/itis/sleeper:1.0.0
	@docker push registry:5000/simcore/services/comp/itis/sleeper:1.0.0
	# completed transfer of images
	@curl -s registry:5000/v2/_catalog | jq '.repositories'
	@curl -s http://registry:5000/v2/simcore/services/comp/itis/sleeper/tags/list?n=50 | jq '.'


.PHONY: inject-templates-in-db
inject-templates-in-db: ## inject project templates
	@docker cp tutorials/sleepers_project_template_sql.csv $$(docker ps -q --filter="name=postgres"):/template_projects_sleepers_project_template_sql.csv
	@docker exec $$(docker ps -q --filter="name=postgres") psql --user scu --dbname simcoredb --command "\copy projects from '/template_projects_sleepers_project_template_sql.csv' csv header;"


.PHONY: test
test: ## test the platform
	# tests
	npm test
	# tests whether tutorial run
	npm run tutorials http://127.0.0.1:9081
