# qooxdoo-kit's versions to use. See https://hub.docker.com/r/itisfoundation/qooxdoo-kit/tags
export QOOXDOO_KIT_TAG=latest

# version controled
export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 .)
export VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')

docker_compose := docker-compose -f tools/docker-compose.yml
docker_file    := tools/qooxdoo-kit/builder/Dockerfile
docker_image   := client/$(subst /Dockerfile,,$(docker_file)):latest


# qx compile --------------------------

qx_packages:
	$(docker_compose) run --rm qooxdoo-kit \
		/bin/sh -c "qx package update && qx package install"

.PHONY: compile-dev
compile-dev: qx_packages ## qx compiles host' 'source' -> host's 'source-output'. Use 'make compile-dev flags=--watch' for continuous compilation.
	# qx compile 'source' $(flags) --> 'source-output' [itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}]
	$(docker_compose) run --rm qooxdoo-kit \
		qx compile $(flags)\
			--set osparc.vcsRef='"${VCS_REF}"' \
			--set osparc.vcsRefClient='"${VCS_REF_CLIENT}"' \
			--set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"' \
			--set osparc.vcsOriginUrl='"${VCS_URL}"'

.PHONY: compile
compile: ## qx compiles host' 'source' -> image's 'build-output'
	# qx compile 'source' within $(docker_image) image  [itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}]
	@docker build -f $(docker_file) -t $(docker_image) --build-arg tag=${QOOXDOO_KIT_TAG} .


# qx serve --------------------------

define qx_serve =
			qx serve $(flags) \
				--set qx.allowUrlSettings=true \
				--set osparc.vcsOriginUrl='"${VCS_URL}"' \
				--set osparc.vcsRef='"${VCS_REF}"' \
				--set osparc.vcsRefClient='"${VCS_REF_CLIENT}"' \
				--set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"'
endef

.PHONY: serve-dev
serve-dev: qx_packages ## compiles & watches host 'source' and serves site in 127.0.0.1:8080. Use this to view the effect of your changes in realtime
	# qx serve $(flags) 'source' --> 'source-output' --> 127.0.0.1:8080
	$(docker_compose) run $(if $(detached),--detach --name=$(detached),--rm) --service-ports qooxdoo-kit $(qx_serve)

.PHONY: serve
serve: compile ## serves site compiled in image in 127.0.0.1:8080
	# qx serve $(flags) 'build-output' within $(docker_image) image --> 127.0.0.1:8080
	docker run --rm -p 8080:8080  $(docker_image) $(qx_serve) --target=build



# misc --------------------------
.PHONY: shell
shell: ## runs /bin/sh in 'itisfoundation/qooxdoo-kit:${QOOXDOO_KIT_TAG}'
	@$(docker_compose) run --rm qooxdoo-kit /bin/sh



.PHONY: info
info: ## this colorful help
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
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


.DEFAULT_GOAL := help

.PHONY: clean
clean: ## clean start
	# tear down docker-compose
	@${docker_compose} down
	# remove build
	@docker image rm -f $(docker_image)
	# remove generated outputs
	@-rm -rf qx_packages .qooxdoo source-output
	# remove unversioned
	@git clean -dXf
