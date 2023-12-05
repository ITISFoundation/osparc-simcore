include ../../../scripts/common.Makefile



.PHONY: openapi.json
openapi.json: ## creates OAS
	example_payment_gateway.py openapi > $@

.PHONY: up-local
up-local:   ## starts payments-gateway sample for local testing
	source $(DOT_ENV_FILE) && export PAYMENTS_USERNAME PAYMENTS_PASSWORD && \
	docker run -it \
		-p 32769:8080 \
		--env "PAYMENTS_SERVICE_API_BASE_URL=http://127.0.0.1:8011" \
		--env "PAYMENTS_USERNAME=$$PAYMENTS_USERNAME" \
		--env "PAYMENTS_PASSWORD=$$PAYMENTS_PASSWORD" \
		local/payments:production\
		example_payment_gateway.py run
