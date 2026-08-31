# Fly-in Automation Makefile

PYTHON := python3
PIP := pip
SRC_DIR := src
TEST_DIR := tests

.PHONY: all install run debug clean lint lint-strict test

all: run

run: install
	$(PYTHON) main.py maps/map.txt --gui

install:
	$(PIP) install -r requirements.txt

debug:
	$(PYTHON) -m pdb main.py maps/map.txt

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict

test:
	pytest $(TEST_DIR) -v