.PHONY: format lint lint-fix test test-cov mypy check all clean

# Format code (ruff replaces black; ruff also handles isort via lint)
format:
	uv run ruff format .

# Lint only (includes isort checks via rule I)
lint:
	uv run ruff check .

# Lint and auto-fix (imports, fixable rules)
lint-fix:
	uv run ruff check . --fix
	uv run ruff format .

# Run tests
test:
	uv run pytest

# Run tests with coverage
test-cov:
	uv run pytest --cov=ttsx --cov-report=term-missing

# Type check
mypy:
	uv run mypy src/

# Full check: format, lint, mypy, test (CI-style)
check: format lint-fix mypy test

# Alias for quick pre-commit style checks (no fix)
all: lint mypy test

# Remove caches and build artifacts
clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
