include ../../../scripts/common.Makefile



.PHONY: openapi.json
openapi.json: ## creates OAS
	example_payment_gateway.py openapi > $@

.PHONY: up-local
up-local:   ## starts payments-gateway sample for local testing
	## Docs in http://127.0.0.1:32769/docs ...
	source $(DOT_ENV_FILE) && export PAYMENTS_USERNAME PAYMENTS_PASSWORD && \
	docker run -it \
		-p 32769:8000 \
		--env "PAYMENTS_SERVICE_API_BASE_URL=http://127.0.0.1:8011" \
		--env "PAYMENTS_USERNAME=$$PAYMENTS_USERNAME" \
		--env "PAYMENTS_PASSWORD=$$PAYMENTS_PASSWORD" \
		--name "example_payment_gateway" \
		local/payments:production \
		example_payment_gateway.py run
