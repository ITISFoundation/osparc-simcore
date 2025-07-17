.DEFAULT_GOAL := help

# qooxdoo-kit's versions to use. See https://hub.docker.com/r/itisfoundation/qooxdoo-kit/tags
export QOOXDOO_KIT_TAG=latest


# version controled
export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 .)
export VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')

docker_compose := docker compose -f tools/docker-compose.yml
docker_file    := tools/qooxdoo-kit/builder/Dockerfile
docker_image   := client/$(subst /Dockerfile,,$(docker_file)):latest

container_name := qooxdoo-compiler

# qx compile --------------------------

qx_packages:
	$(docker_compose) run --rm qooxdoo-kit \
		/bin/sh -c "qx package update && qx package install"

source-output:
	# making fast a folder to allow volume binding in dev-mode
	mkdir $@

.PHONY: compile-dev
compile-dev: qx_packages source-output ## qx compiles host' 'source' -> host's 'source-output'. Use 'make compile-dev flags=--watch' for continuous compilation.
	# qx compile 'source' $(flags) --> 'source-output' [itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}]
	$(docker_compose) run --detach --rm --name=$(container_name) qooxdoo-kit \
		qx compile $(flags) \
			--set-env osparc.vcsOriginUrl="${VCS_URL}" \
			--set-env osparc.vcsRef="${VCS_REF}" \
			--set-env osparc.vcsRefClient="${VCS_REF_CLIENT}" \
			--set-env osparc.vcsStatusClient="${VCS_STATUS_CLIENT}"

.PHONY: follow-dev-logs
follow-dev-logs: ## follow the logs of the qx compiler
	@docker logs --follow $(container_name)


.PHONY: compile touch upgrade
compile: ## qx compiles host' 'source' -> image's 'build-output'
	# qx compile 'source' within $(docker_image) image  [itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}]
	@docker buildx build \
		--load \
		--file $(docker_file) \
		--tag $(docker_image) \
		--build-arg tag=${QOOXDOO_KIT_TAG} \
		--build-arg VCS_REF=${VCS_REF} \
		--build-arg VCS_REF_CLIENT=${VCS_REF_CLIENT} \
		--build-arg VCS_STATUS_CLIENT=${VCS_STATUS_CLIENT} \
		--build-arg VCS_URL=${VCS_URL} \
		--target=build-client .
	python ./scripts/post-compile.py

touch: ## minimal image build with /project/output-build inside
	# touch /project/output-build such that multi-stage 'services/web/Dockerfile' can build development target (fixes #1097)
	@docker buildx build \
		--load \
		--file $(docker_file) \
		--tag $(docker_image) \
		--build-arg tag=${QOOXDOO_KIT_TAG} \
		--target=touch \
		.

upgrade: ## upgrade to official version of the tool
	# upgrading to ${QOOXDOO_KIT_TAG}
	@${docker_compose} pull

.PHONY: down
down: ## tear down docker-compose
	@${docker_compose} down --remove-orphans

# qx serve --------------------------

define qx_serve =
			qx serve $(flags) \
				--set qx.allowUrlSettings=true \
				--set-env osparc.vcsOriginUrl="${VCS_URL}" \
				--set-env osparc.vcsRef="${VCS_REF}" \
				--set-env osparc.vcsRefClient="${VCS_REF_CLIENT}" \
				--set-env osparc.vcsStatusClient="${VCS_STATUS_CLIENT}"
endef

.PHONY: serve-dev
serve-dev: qx_packages ## compiles & watches host 'source' and serves site in 127.0.0.1:8080. Use this to view the effect of your changes in realtime
	# qx serve $(flags) 'source' --> 'source-output' --> 127.0.0.1:8080
	$(docker_compose) run $(if $(detached),--detach --name=$(detached),--rm) --service-ports qooxdoo-kit $(qx_serve)

.PHONY: serve
serve: compile ## serves site compiled in image in 127.0.0.1:8080
	# qx serve $(flags) 'build-output' within $(docker_image) image --> 127.0.0.1:8080
	docker run --rm -p 8080:8080  $(docker_image) $(qx_serve) --target=build


# qx translate --------------------------

define qx_translate_extract =
			qx compile --update-po-files
endef

.PHONY: translate-extract
translate-extract: translate-extract ## the generated .po files goes to source/translation https://qooxdoo.org/documentation/v7.8/#/development/howto/internationalization?id=translation
	# qx compile --update-po-files
	$(docker_compose) run $(if $(detached),--detach --name=$(detached),--rm) qooxdoo-kit $(qx_translate_extract)


# misc --------------------------
.PHONY: shell
shell: ## runs /bin/sh in 'itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}'
	@$(docker_compose) run --rm qooxdoo-kit /bin/sh


.PHONY: info
info: ## displays info about toolkit and build images
	# toolkit image 'itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}'
	@docker images itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}
	@docker image inspect itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG} $(if jq,| jq .[0].ContainerConfig.Labels,)
	# build image '$(docker_image)'
	@docker images $(docker_image)


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes to qx compile/serve web client using 'itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}'"
	@docker image inspect itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG} $(if jq,| jq .[0].ContainerConfig.Labels,)
	@echo ""
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


.PHONY: clean clean-files clean-images
clean-files:
	# remove generated outputs
	@-rm -rf qx_packages .qooxdoo source-output
	# remove unversioned
	@git clean -dXf

clean-images:
	# tear down docker-compose
	@${docker_compose} down
	# remove build
	@docker image rm -f $(docker_image)

clean: clean-images clean-files ## Forces clean of all outputs (files and images)
