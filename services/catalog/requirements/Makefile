.PHONY: all check clean help

objects = $(wildcard *.in)
outputs := $(objects:.in=.txt)

all: $(outputs) ## pip-compiles all requirements/*.in -> requirements/*.txt

%.txt: %.in
	pip-compile --output-file $@ $<

_test.txt: _base.txt


check: ## Checks whether pip-compile is installed
	@which pip-compile > /dev/null


clean: check ## Cleans all requirements/*.txt
	- rm $(outputs)


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
