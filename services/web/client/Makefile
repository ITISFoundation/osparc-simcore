export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 .)
export VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')

docker_compose=docker-compose -f tools/docker-compose.yml
docker_file=tools/qooxdoo-kit/compile/Dockerfile
docker_image=$(subst /Dockerfile,,$(docker_file)):last



qx_packages:
	$(docker_compose) run --rm qooxdoo-kit \
		/bin/sh -c '"qx package update && qx package install"'

.PHONY: compile-dev
compile-dev: qx_packages ## qx compiles front-end's code [dev]
	$(docker_compose) run --rm qooxdoo-kit \
		qx compile \
			--set osparc.vcsRef='"${VCS_REF}"' \
			--set osparc.vcsRefClient='"${VCS_REF_CLIENT}"' \
			--set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"' \
			--set osparc.vcsOriginUrl='"${VCS_URL}"'

.PHONY: compile
compile: ## qx compiles source
	# compiling in `$(docker_image)`
	docker build -f ${docker_file} -t ${docker_image} .



.PHONY: serve-dev
serve-dev: qx_packages ## compiles, watches and serves front-end's code
	$(docker_compose) run --rm --service-ports qooxdoo-kit \
		qx serve \
			--set qx.allowUrlSettings=true
      --set osparc.vcsOriginUrl='"${VCS_URL}"'
      --set osparc.vcsRef='"${VCS_REF}"'
      --set osparc.vcsRefClient='"${VCS_REF_CLIENT}"'
      --set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"'

.PHONY: serve
serve: compile ## serves front-end's code in container
	docker run --rm -p 8080:8080 ${docker_image} \
		qx serve \
			--set qx.allowUrlSettings=true
      --set osparc.vcsOriginUrl='"${VCS_URL}"'
      --set osparc.vcsRef='"${VCS_REF}"'
      --set osparc.vcsRefClient='"${VCS_REF_CLIENT}"'
      --set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"'

.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## This help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help

.PHONY: clean
clean: ## clean start
	# tear down docker-compose
	@${docker_compose} down
	# remove
	@-rm -rf qx_packages .qooxdoo
	# remove unversioned
	@git clean -dXf
