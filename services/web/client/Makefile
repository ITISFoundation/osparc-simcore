VCS_URL:=$(shell git config --get remote.origin.url)
VCS_REF:=$(shell git rev-parse --short HEAD)
VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 .)
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


.PHONY: build-devel
# target: build-devel: – Builds dev container
build-devel:
	export BUILD_TARGET=development; docker-compose build


.PHONY: build
# target: build: – Builds container
build:
	export BUILD_TARGET=build; docker-compose build
	docker run -it client_qx:build /bin/sh -c "ls -l build-output;cat build-output/version.txt"


.PHONY: clean
# target: clean: – Cleans images and current dir outputs
clean:
	@docker-compose down
	@docker image rm -f client_qx:build 2> /dev/null
	@docker image rm -f client_qx:development 2> /dev/null
	@git clean -dxf ${CURDIR}


.PHONY: compile
# target: compile: – Compiles front-end's code [dev]
compile:
	export BUILD_TARGET=development; \
		docker-compose run --service-ports qx compile \
			--set osparc.vcsRef='"${VCS_REF}"' \
			--set osparc.vcsRefClient='"${VCS_REF_CLIENT}"' \
			--set osparc.vcsStatusClient='"${VCS_STATUS_CLIENT}"' \
			--set osparc.vcsOriginUrl='"${VCS_URL}"'


.PHONY: serve
# target: serve: – Compiles, watches and serves front-end's code [dev]
serve:
	export BUILD_TARGET=development; \
		docker-compose run --service-ports qx
