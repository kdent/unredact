.PHONY: check format fix docs
SRC = $(wildcard src/unredact/*.py)

# Lints the code using Ruff (returns non-zero if errors are found)
check:
	ruff check src/unredact

# Formats the code and verifies formatting
format:
	ruff format src/unredact --check

# Automatically fixes fixable errors (e.g., removing unused imports)
fix:
	ruff check --fix src/unredact
	ruff format src/unredact

docs:
	$(MAKE) docs/unredact

docs/unredact: $(SRC)
	pdoc --html --output-dir docs --force unredact

clean-docs:
	rm -rf docs/unredact

test:
	python -m pytest tests/test_state_stack.py -v
	python -m pytest tests/test_document_state.py -v
	python -m pytest tests/test_core.py -v
