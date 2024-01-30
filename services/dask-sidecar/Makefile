#
# DEVELOPMENT recipes for Workflows manager service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


TEMP_DIR := $(shell mktemp -d -t dask-docker-XXX)

.PHONY: settings-schema.json
settings-schema.json: ## [container] dumps json-shcema of this service settings
	# Dumping settings schema of ${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_IMAGE_TAG}
	@docker run \
		--entrypoint="${APP_CLI_NAME}" \
		${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_IMAGE_TAG} \
		settings --as-json-schema \
		| sed --expression='1,/{/ {/{/!d}' \
		> $@
	# Dumped '$(CURDIR)/$@'

.dask-certificates:
	# create new certificates
	mkdir --parents $@
	# Set variables for the key and certificate paths
	# Run openssl without prompts using the -subj argument to pass subject information
	key_path="$@/dask-key.pem" && \
	cert_path="$@/dask-cert.pem" && \
	subj="/C=CH/ST=ZH/L=ZH/O=ITIS/OU=OSPARC/CN=osparc.io" && \
	openssl req -x509 -newkey rsa:4096 -nodes -keyout "$$key_path" -out "$$cert_path" -days 365 -subj "$$subj"


.PHONY: certificates info-certificates clean-certificates

certificates: .dask-certificates ## creates a self-signed certificate for use with dask communication
	# validating certificates
	@openssl verify -CAfile $</dask-cert.pem $</dask-cert.pem

info-certificates: .dask-certificates ## shows information about the self-signed certificate
	openssl x509 -in $</dask-cert.pem -text -noout

clean-certificates: ## deletes the self-signed certificate
	@echo "This will remove the Dask certificates. If you have running dask backend using these certificates, you will not be able to connect anymore"
	@read -p "Are you sure? [y/N]: " confirm && [[ $$confirm == [yY] || $$confirm == [yY][eE][sS] ]] || exit 1
	@read -p "Are you absolutely sure? This cannot be undone. [y/N]: " confirm_again && [[ $$confirm_again == [yY] || $$confirm_again == [yY][eE][sS] ]] || exit 1
	rm -rf .dask-certificates
	@echo "Certificates have been removed."
