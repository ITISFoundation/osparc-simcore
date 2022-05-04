
SHELL = /bin/bash
.DEFAULT_GOAL := help

BASE_ADDRESS = http://localhost:8000/v1/

.PHONY: save-state
save-state:  ## start saving the state of this service
	@echo ">>>>> Expect a 204 reply if OK <<<<<"
	curl -v -X POST ${BASE_ADDRESS}/containers/state:save


.PHONY: push-outputs
push-outputs:  ## push the outputs for this service
	@echo ">>>>> Expect a 204 reply if OK <<<<<"
	curl -v -X POST ${BASE_ADDRESS}/containers/ports/outputs:push


.PHONY: help
help:   ## this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| sed -n 's/^\(.*\): \(.*\)##\(.*\)/\1\t\3/p'


