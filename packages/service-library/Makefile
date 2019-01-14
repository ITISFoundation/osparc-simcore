
clean:
	@rm -rf src/*.egg-info
	@rm -rf .eggs
	@rm -rf `find . -name __pycache__`
	@rm -f `find . -type f -name '*.py[co]' `
	@python3 setup.py clean

pip-deduce-requirements:
	@pip install pipreqs
	@pipreqs src/servicelib --savepath requirements/requirements.ignore

pip-compile:
	@pip install pip-tools
	@pip-compile --generate-hashes --output-file requirements/prod.txt setup.py

install:
	@pip install -U pip
	@pip install -Ur requirements/dev.txt


.PHONY: all pip-compile pip-deduce-requirements clean
