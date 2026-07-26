PYTHON = uv run python
CACHE_DIRS = .pytest_cache .mypy_cache .uv_cache

.PHONY: run run-gui install test debug clean lint

run:
	$(PYTHON) -m src data/map.txt --viz terminal

run-gui:
	$(PYTHON) -m src data/map.txt --viz gui

install:
	uv sync

test:
	uv run pytest tests/

debug:
	$(PYTHON) -m pdb -m src

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@for dir in $(CACHE_DIRS); do \
		if [ -d $$dir ]; then \
			rm -rf $$dir; \
		fi; \
	done

lint:
	uv run flake8 src
	uv run mypy src --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
