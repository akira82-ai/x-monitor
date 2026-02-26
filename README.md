# x-monitor

X (Twitter) User Monitoring CLI Dashboard - A TUI application for monitoring Twitter users via Nitter RSS feeds.

## Features

- **TUI Dashboard** - Clean terminal interface with minimal design
- **Real-time Polling** - Configurable polling interval for new tweets
- **New Tweet Indicators** - 🔔 marks unread tweets, cleared when you browse
- **Multiple Users** - Monitor multiple Twitter handles simultaneously
- **Notifications** - Terminal alerts for new tweets
- **No API Keys** - Uses public Nitter RSS feeds
- **Simple & Fast** - Python implementation with minimal dependencies
- **Keyboard Shortcuts** - Always visible at the bottom of the screen

## UI Design

The interface uses clean lines and borders instead of color blocks:

```
┌─────────────────────────────────────────────────────────────┐
│ x-monitor | ▶ • 🔔 4 条新 • 50 条 • 1/2 页 • 34秒前          │
├─────────────────────────────────────────────────────────────┤
│  User         Content                          Date         │
│  @karpathy    🔔 Just shipped a new feature! 🚀   02-26     │
│  @suhail      🔔 Working on AI research...        02-26     │
│  @user        🔁 Retweeted something...          02-25     │
├─────────────────────────────────────────────────────────────┤
│ Q:退出  R:刷新  Space:暂停  ↑↓:选择  N/P:翻页  g/G:首尾    │
└─────────────────────────────────────────────────────────────┘
```

**Legend:**
- 🔔 = New/unread tweet
- 🔁 = Retweet

See [UI_DESIGN.md](UI_DESIGN.md) for detailed design documentation.

## Installation

```bash
# Using the run script (recommended - handles everything automatically)
./run.sh

# Or install manually with pip
pip3 install prompt_toolkit feedparser httpx toml wcwidth
```

## Usage

### Quick Start

```bash
# Using the run script (recommended)
./run.sh

# Or using Make
make install
make config  # Edit config.toml with your users
make run

# Or manually with virtual environment
source .venv/bin/activate
python3 main.py
```

### Demo Mode

Test the UI without network:

```bash
# Using demo script (easiest)
./demo.sh

# Or manually
source .venv/bin/activate
python3 demo.py
```

### Command Line Options

```bash
# Activate virtual environment first
source .venv/bin/activate

# Create a sample config
python3 main.py --create-config

# Run with default config.toml
python3 main.py

# Run with custom config file
python3 main.py /path/to/config.toml

# Show help
python3 main.py --help
```

## Key Bindings

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `R` | Refresh tweets immediately |
| `Space` | Pause/Resume monitoring |
| `↓` / `J` | Move down (marks current tweet as read) |
| `↑` / `K` | Move up (marks current tweet as read) |
| `N` / `PageDown` | Next page |
| `P` / `PageUp` | Previous page |
| `G` | Jump to bottom |
| `g` | Jump to top |

## Configuration

Create a `config.toml` file:

```toml
[general]
poll_interval_sec = 60
nitter_instance = "https://nitter.net"
max_tweets = 400

[users]
handles = ["karpathy", "suhail", "another_user"]

[notification]
enable = true
sound = true
flash = true
desktop = false

[ui]
theme = "dark"
show_timestamps = true
auto_scroll = true
```

### Configuration Options

- `poll_interval_sec`: How often to check for new tweets (min: 10)
- `nitter_instance`: Which Nitter mirror to use
- `max_tweets`: Maximum tweets to keep in memory
- `handles`: List of Twitter usernames (without @)
- `enable`: Enable notifications
- `sound`: Terminal bell on new tweets
- `flash`: Visual alert on new tweets

## Nitter Instances

If nitter.net is slow or unavailable, try other instances:
- https://nitter.net
- https://nitter.poast.org
- https://nitter.privacydev.net
- https://nitter.mint.lgbt

See the [Nitter wiki](https://github.com/zedeus/nitter/wiki/Instances) for more.

## Troubleshooting

### Network Issues

If you encounter network errors:

1. **Check Nitter instance availability**: Try accessing the Nitter instance URL in your browser
2. **Try a different instance**: Update `nitter_instance` in `config.toml`
3. **Check your network**: Ensure you have internet connectivity
4. **Proxy issues**: The app disables proxy by default. If you need proxy support, modify `src/fetcher.py`

### No Tweets Showing

- The user might not have recent tweets
- The Nitter instance might be rate-limited
- Try a different Nitter instance
- Wait a few minutes and try again

### Testing

Run the test suite to verify components:

```bash
source .venv/bin/activate
python3 test.py
```

### Demo Mode

Test the UI without network access:

```bash
# Using demo script (easiest)
./demo.sh

# Or manually
source .venv/bin/activate
python3 demo.py
```

This generates fake tweets for UI testing.

## Architecture

```
x-monitor/
├── src/
│   ├── __init__.py
│   ├── config.py      # TOML configuration
│   ├── types.py       # Data structures
│   ├── fetcher.py     # RSS fetching (feedparser + httpx)
│   ├── monitor.py     # Polling logic (asyncio)
│   └── ui.py          # TUI (prompt_toolkit)
├── config.toml
├── main.py
├── pyproject.toml
└── README.md
```

## License

MIT
