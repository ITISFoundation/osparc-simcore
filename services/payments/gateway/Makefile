include ../../../scripts/common.Makefile



.PHONY: run-devel
run-devel: ## runs example_payment_gateway server
	# SEE http://127.0.0.1:8000/docs
	set -o allexport; source .env-secret; set +o allexport; \
	uvicorn example_payment_gateway:the_app --reload

.PHONY: openapi.json
openapi.json: ## creates OAS
	@set -o allexport; source .env-secret; set +o allexport; \
	python example_payment_gateway.py openapi > $@
