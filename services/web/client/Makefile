VCS_REF:=$(shell git rev-parse --short HEAD)
VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 .)
BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export VCS_REF
export VCS_REF_CLIENT
export BUILD_DATE

info:
	@echo '+ vcs ref '
	@echo '  - all       : ${VCS_REF}'
	@echo '  - web/client: ${VCS_REF_CLIENT}'
	@echo '  - '$(shell if [[ -z $(git status -s) ]]; then echo clean; else echo 'modified/untracked'; fi)
	@echo '+ date        : ${BUILD_DATE}'


build-devel:
	export BUILD_TARGET=development; docker-compose build

build:
	export BUILD_TARGET=build; docker-compose build

compile:
	docker-compose run --service-ports \
		qx compile --set osparc.vcsRef='"${VCS_REF}"' --set osparc.vcsRefClient='"${VCS_REF_CLIENT}"'

serve:
	docker-compose run --service-ports \
		qx serve --set qx.allowUrlSettings=true --set osparc.vcsRef='"${VCS_REF}"' --set osparc.vcsRefClient='"${VCS_REF_CLIENT}"'
