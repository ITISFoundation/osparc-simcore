include ../../../scripts/common.Makefile



.PHONY: run-devel
run-devel: ## runs fake_payment_gateway server
	# SEE http://127.0.0.1:8000/docs
	set -o allexport; source .env-secret; set +o allexport; \
	uvicorn fake_payment_gateway:the_app --reload
