.PHONY: all check clean help

objects = $(wildcard *.in)
outputs := $(objects:.in=.txt)

# target: all – pip-compiles all requirements/*.in -> requirements/*.txt
all: $(outputs)

%.txt: %.in
	pip-compile --output-file $@ $<

_test.txt: _base.txt

# target: check – Checks whether pip-compile is installed
check:
	@which pip-compile > /dev/null

# target: clean – Cleans all requirements/*.txt
clean: check
	- rm $(outputs)

# target: help – Display all callable targets
help:
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| sed -r "s/^\s*#\s*target\s*:\s*//g"
	@echo
