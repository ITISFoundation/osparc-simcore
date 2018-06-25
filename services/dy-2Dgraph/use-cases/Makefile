PLATFORM := $(shell uname)
VERSION := $(shell cat /proc/version)
ifneq (,$(findstring Microsoft,$(VERSION)))
export docker-compose=docker-compose.exe
else
export docker-compose=docker-compose
endif


build:	
	${docker-compose} -f docker-compose.yml build --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

rebuild:
	${docker-compose} -f docker-compose.yml build --no-cache --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

up:
	${docker-compose} -f docker-compose.yml up

down:
	${docker-compose} -f docker-compose.yml down

build-devel:
	${docker-compose} -f docker-compose.yml -f docker-compose.devel.yml build --build-arg VCS_REF=`git rev-parse --short HEAD` BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

rebuild-devel:
	${docker-compose} -f docker-compose.yml -f docker-compose.devel.yml build --no-cache --build-arg VCS_REF=`git rev-parse --short HEAD` BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

up-devel:
	${docker-compose} -f docker-compose.yml -f docker-compose.devel.yml up

down-devel:
	${docker-compose} -f docker-compose.yml -f docker-compose.devel.yml down