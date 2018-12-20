
clean:
	@rm -rf `find . -name __pycache__`
	@rm -f `find . -type f -name '*.py[co]' `
	@python setup.py clean

pip-compile:
	@pip-compile --generate-hashes --output-file requirements/staging.txt setup.py

install:
	@pip install -U pip
	@pip install -Ur requirements/dev.txt

.PHONY: all pip-compile clean
