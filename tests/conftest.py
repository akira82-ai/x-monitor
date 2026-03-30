"""Test configuration and fixtures for x-monitor tests."""

import sys
from pathlib import Path

# Add the repository root so tests can import the packaged modules via `src.*`.
sys.path.insert(0, str(Path(__file__).parent.parent))
