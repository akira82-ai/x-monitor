.PHONY: help install run test demo clean config

help:
	@echo "x-monitor - Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make config     - Create sample config.toml"
	@echo "  make run        - Run the application"
	@echo "  make demo       - Run in demo mode (fake data)"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Clean up generated files"

install:
	@echo "Installing dependencies..."
	@python3 -m venv .venv || true
	@.venv/bin/pip install -q textual feedparser httpx toml
	@echo "✓ Dependencies installed"

config:
	@.venv/bin/python3 main.py --create-config
	@echo "✓ Created config.toml"
	@echo "Edit config.toml with your Twitter handles"

run:
	@.venv/bin/python3 main.py config.toml

demo:
	@.venv/bin/python3 demo.py

test:
	@.venv/bin/python3 test.py

clean:
	@rm -rf .venv __pycache__ src/__pycache__
	@echo "✓ Cleaned up"
