#
# References:
#
#  https://github.com/jazzband/pip-tools
#  https://alexwlchan.net/2017/10/pip-tools/
#  https://hynek.me/articles/python-app-deps-2018/#pip-tools-everything-old-is-new-again
#
#
.PHONY: reqs check clean help
.DEFAULT_GOAL := help

objects = $(wildcard *.in)
outputs := $(objects:.in=.txt)

reqs: $(outputs) ## pip-compiles all requirements/*.in -> requirements/*.txt

%.txt: %.in
	pip-compile --upgrade --build-isolation --output-file $@ $<

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
