export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 .)
export VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')

docker_compose=docker-compose -f tools/docker-compose.yml



.PHONY: compile
compile-dev: ## qx compiles front-end's code [dev]
	$(docker_compose) run --rm qooxdoo-kit \
		qx compile \
			--set osparc.vcsRef='"${VCS_REF}"' \
			--set osparc.vcsRefClient='"${VCS_REF_CLIENT}"' \
			--set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"' \
			--set osparc.vcsOriginUrl='"${VCS_URL}"'


.PHONY: serve
serve-dev: ## compiles, watches and serves front-end's code
	$(docker_compose) run --rm --service-ports qooxdoo-kit \
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
clean: ## clean down and unversioned files
	@docker-compose down
	@git clean -dxf ${CURDIR}
