# How to Run x-monitor

## Quick Start (Easiest Way)

```bash
# Demo mode (test UI, no network needed)
./demo.sh

# Real mode (fetch tweets)
./run.sh
```

These scripts automatically handle virtual environment activation.

## Manual Method

If you prefer to run manually:

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run demo mode
python3 demo.py

# 3. Or run real mode
python3 main.py
```

**Important:** Always activate the virtual environment first with `source .venv/bin/activate`

## First Time Setup

If you haven't set up the project yet:

```bash
# 1. Create virtual environment (if not exists)
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies
pip3 install prompt_toolkit feedparser httpx toml wcwidth pyperclip

# 4. Create config file
python3 main.py --create-config

# 5. Edit config.toml with your favorite Twitter users
nano config.toml  # or use any text editor

# 6. Run the application
python3 main.py
```

## Using the Startup Script

The easiest way:

```bash
./run.sh
```

This script will:
- Check and create virtual environment if needed
- Install dependencies if needed
- Create config if needed
- Run the application

## Using Make

```bash
# Install dependencies
make install

# Create config
make config

# Run the app
make run

# Run demo mode
make demo

# Run tests
make test
```

## Keyboard Shortcuts

Once the app is running:

| Key | Action |
|-----|--------|
| `Q` | Quit the application |
| `R` | Refresh tweets now |
| `Space` | Pause/Resume monitoring |
| `D` | Toggle details panel |
| `↑` or `K` | Move up in tweet list |
| `↓` or `J` | Move down in tweet list |
| `g` | Jump to top |
| `G` | Jump to bottom |

## Troubleshooting

### "ModuleNotFoundError: No module named 'toml'"

You need to activate the virtual environment first:
```bash
source .venv/bin/activate
python3 demo.py
```

Or use the provided scripts:
```bash
./demo.sh    # For demo mode
./run.sh     # For real mode
```

### "command not found: python"

Use `python3` instead:
```bash
python3 demo.py
python3 main.py
```

### "No module named 'prompt_toolkit'"

Install dependencies:
```bash
source .venv/bin/activate
pip3 install prompt_toolkit feedparser httpx toml wcwidth pyperclip
```

### "No such file or directory: .venv"

Create virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install prompt_toolkit feedparser httpx toml wcwidth pyperclip
```

### Network errors

Try demo mode first to test the UI:
```bash
python3 demo.py
```

## System Requirements

- Python 3.10 or higher (3.9 may work)
- Terminal with Unicode support
- Internet connection (for real data, not needed for demo)

## Check Your Python Version

```bash
python3 --version
```

Should show Python 3.9 or higher.
