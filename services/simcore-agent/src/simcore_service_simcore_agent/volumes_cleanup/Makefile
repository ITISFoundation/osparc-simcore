-include .env

IMAGE_NAME:=dy-volume-cleanup

.PHONY: build
build:		# builds docker image
	docker build -t ${IMAGE_NAME} .

.PHONY: env-devel
env-devel:	# compiles 
	cp .env-devel .env

.PHONY: dev-run
dev-run:	# runs in devel mode
	docker run --interactive --tty --rm \
		--volume /var/lib/docker/volumes/:/var/lib/docker/volumes/ \
		--volume /var/run/docker.sock:/var/run/docker.sock \
		${IMAGE_NAME} dyvc ${S3_ENDPOINT} ${S3_ACCESS_KEY} ${S3_SECRET_KEY} ${S3_BUCKET} ${S3_PROVIDER} --s3-region ${S3_REGION}

.PHONY: codestyle
codestyle:	# runs codestyle enforcement
	poetry run isort .
	poetry run black .
	poetry run pylint dy_volumes_cleanup tests

