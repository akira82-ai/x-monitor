.PHONY: help install install-dev run test demo clean config

help:
	@echo "x-monitor - Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make install-dev  - Install dependencies with dev tools (pytest)"
	@echo "  make config       - Create sample config.toml"
	@echo "  make run          - Run the application"
	@echo "  make demo         - Run in demo mode (fake data)"
	@echo "  make test         - Run tests"
	@echo "  make clean        - Clean up generated files"

install:
	@echo "Installing dependencies..."
	@python3 -m venv .venv || true
	@.venv/bin/pip install -q prompt_toolkit feedparser httpx toml wcwidth pyperclip
	@echo "✓ Dependencies installed"

install-dev:
	@echo "Installing dependencies with dev tools..."
	@python3 -m venv .venv || true
	@.venv/bin/pip install -q prompt_toolkit feedparser httpx toml wcwidth pyperclip pytest pytest-cov pytest-asyncio
	@echo "✓ Dependencies installed (including dev tools)"

config:
	@.venv/bin/python3 main.py --create-config
	@echo "✓ Created config.toml"
	@echo "Edit config.toml with your Twitter handles"

run:
	@.venv/bin/python3 main.py config.toml

demo:
	@.venv/bin/python3 demo.py

test:
	@echo "Running tests..."
	@.venv/bin/pytest tests/ -v
	@echo "✓ Tests completed"

test-cov:
	@echo "Running tests with coverage..."
	@.venv/bin/pytest tests/ -v --cov=src --cov-report=term-missing
	@echo "✓ Tests completed with coverage"

clean:
	@rm -rf .venv __pycache__ src/__pycache__ tests/__pycache__
	@rm -rf .pytest_cache .coverage htmlcov/
	@echo "✓ Cleaned up"
