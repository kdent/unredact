# Here is some general information on Makefile's so that you can grow this out:
# https://www.gnu.org/software/make/manual/html_node/Introduction.html

.PHONY: lint
lint:
	black ./
	isort ./
	ruff /
