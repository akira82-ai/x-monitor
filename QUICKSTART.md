# Quick Start Guide

## 1. Installation

```bash
# Clone or download the project
cd x-monitor

# Install dependencies
make install
# or
./run.sh
```

## 2. Configuration

```bash
# Create config file
make config
# or
python main.py --create-config
```

Edit `config.toml`:

```toml
[users]
handles = ["karpathy", "suhail", "your_favorite_user"]
```

## 3. Run

```bash
# Using run script (easiest)
./run.sh

# Using Make
make run

# Using Python directly
python3 main.py
```

## 4. Usage

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `R` | Refresh now |
| `↓` or `J` | Next tweet |
| `↑` or `K` | Previous tweet |
| `←` or `PgUp` | Previous page |
| `→` or `PgDn` | Next page |
| `/` | Search/filter |
| `U` | Filter current user |
| `O` | Open selected tweet |
| `C` | Copy selected tweet |
| `Alt+↑/↓` | Scroll details |
| `Alt+R` | Mark all as read |
| `G` | Jump to bottom |
| `g` | Jump to top |

### First Time Setup

1. Run `./run.sh` - it will create a sample config
2. Edit `config.toml` with your favorite Twitter users
3. Run `./run.sh` again
4. Enjoy real-time tweet monitoring!

## 5. Demo Mode

Test the UI without network:

```bash
python3 demo.py
```

## 6. Troubleshooting

### No tweets showing?

1. Check if the Nitter instance is working (visit it in browser)
2. Try a different instance in `config.toml`:
   ```toml
   nitter_instance = "https://nitter.poast.org"
   ```
3. Wait a few minutes (rate limiting)

### Network errors?

- Check your internet connection
- Try a different Nitter instance
- Some instances may be down temporarily

### UI not working?

- Make sure you have Python 3.10+
- Reinstall dependencies: `make install`
- Try demo mode: `python3 demo.py`

## 7. Advanced

### Custom polling interval

```toml
[general]
poll_interval_sec = 30  # Check every 30 seconds
```

### Disable notifications

```toml
[notification]
enable = false
```

### More tweets in memory

```toml
[general]
max_tweets = 100  # Keep 100 tweets
```

## Need Help?

- Read the full [README.md](README.md)
- Check [OVERVIEW.md](OVERVIEW.md) for technical details
- Run tests: `python3 -m pytest tests/`
