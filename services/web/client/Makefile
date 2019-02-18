VCS_URL:=$(shell git config --get remote.origin.url)
VCS_REF:=$(shell git rev-parse --short HEAD)
VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 .)
#VCS_STATUS_CLIENT:=$(shell if [[ -z $(git status -s) ]]; then echo clean; else echo 'modified/untracked'; fi)

VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')
BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export VCS_URL
export VCS_REF
export VCS_REF_CLIENT
export VCS_STATUS_CLIENT
export BUILD_DATE

.PHONY: info
# target: info: – Displays environ variables
info:
	@echo '+ vcs ref '
	@echo '  - origin    : ${VCS_URL}'
	@echo '  - all       : ${VCS_REF}'
	@echo '  - web/client (${VCS_STATUS_CLIENT}): ${VCS_REF_CLIENT}'
	@echo '+ date        : ${BUILD_DATE}'


.PHONY: info
# target: info: – Displays environ variables
build-devel:
	export BUILD_TARGET=development; docker-compose build

build:
	export BUILD_TARGET=build; docker-compose build

compile:
	docker-compose run --service-ports qx compile \
		--set osparc.vcsRef='"${VCS_REF}"' \
		--set osparc.vcsRefClient='"${VCS_REF_CLIENT}"' \
		--set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"'
		--set osparc.vcsOriginUrl='"${VCS_URL}"'

serve:
	docker-compose run --service-ports qx serve \
		--set qx.allowUrlSettings=true \
		--set osparc.vcsRef='"${VCS_REF}"' \
		--set osparc.vcsRefClient='"${VCS_REF_CLIENT}"'\
		--set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"' \
		--set osparc.vcsOriginUrl='"${VCS_URL}"'
