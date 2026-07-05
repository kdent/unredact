.PHONY: check format fix

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

test:
	python -m pytest tests/test_state_stack.py -v
	python -m pytest tests/test_document_state.py -v
	python -m pytest tests/test_core.py -v
