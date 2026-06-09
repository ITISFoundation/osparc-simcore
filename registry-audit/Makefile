.PHONY: build run check clean

IMAGE_NAME := registry-audit

# Load .env file if it exists
ifneq (,$(wildcard .env))
  include .env
  export
endif

build:
	docker build -t $(IMAGE_NAME) .

run:
	@test -f .env || (echo "ERROR: .env file not found. Copy .env.example to .env and fill in credentials." && exit 1)
	@docker run --rm \
		-e REGISTRY_URL="$(REGISTRY_URL)" \
		-e REGISTRY_USER="$(REGISTRY_USER)" \
		-e REGISTRY_PASSWORD="$(REGISTRY_PASSWORD)" \
		$(IMAGE_NAME)

check: build run

clean:
	docker rmi $(IMAGE_NAME) 2>/dev/null || true
