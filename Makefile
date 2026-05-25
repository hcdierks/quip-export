VENV := .venv/bin
# WeasyPrint needs Homebrew's pango/glib on macOS
DYLD_LIBRARY_PATH := /opt/homebrew/lib

.PHONY: test lint typecheck install

install:
	python3 -m venv .venv
	$(VENV)/pip install --upgrade pip --quiet
	$(VENV)/pip install -e ".[dev]"

test:
	DYLD_LIBRARY_PATH=$(DYLD_LIBRARY_PATH) $(VENV)/pytest

lint:
	$(VENV)/ruff check src tests

typecheck:
	$(VENV)/mypy src
