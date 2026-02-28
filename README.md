# x-monitor

X (Twitter) User Monitoring CLI Dashboard - A TUI application for monitoring Twitter users via Nitter RSS feeds.

## Features

- **TUI Dashboard** - Clean terminal interface with minimal design
- **Real-time Polling** - Configurable polling interval for new tweets
- **New Tweet Indicators** - 🔔 marks unread tweets, cleared when you browse
- **Multiple Users** - Monitor multiple Twitter handles simultaneously
- **Search & Filter** - Keyword search and user filtering (press `/` or `u`)
- **Open in Browser** - Directly open tweet URLs in browser (press `o`)
- **Details Panel** - Scrollable details panel with Alt+↑/↓
- **Config Hot Reload** - Reload config without restarting (Alt+R or F5)
- **Loading & Error States** - Visual feedback for polling status
- **Notifications** - Terminal alerts for new tweets (bell, visual flash, window title badge, macOS Dock badge)
- **Burst Detection** - Triggers 3× bell when 5+ tweets arrive within 60 seconds
- **No API Keys** - Uses public Nitter RSS feeds
- **Simple & Fast** - Python implementation with minimal dependencies
- **Keyboard Shortcuts** - Always visible at the bottom of the screen
- **State Persistence** - Automatically saves tweet history between sessions
- **Incremental Save** - Only new tweets are saved to disk for better performance
- **Accurate Emoji Rendering** - ZWJ emoji sequences (e.g. 🧑‍💻) display correctly without column overflow
- **Startup Progress** - Shows per-user loading progress (`Loading tweets... 1/9`) before the TUI starts

## UI Design

The interface uses clean lines and borders instead of color blocks:

```
┌──────────────────────────────────┬──────────────────────────────────┐
│ x-monitor | ▶ • 🔔 4 条新 • 50 条 │ @karpathy                        │
│ • 1/2 页 • 34秒前                 │ 🔁 转推                          │
├──────────────────────────────────┤ 发布时间: 2025-02-26 10:30:00    │
│  User         Content    Date    │ URL: https://x.com/karpathy/...  │
│  @karpathy   Just shipped  02-26 │ ──────────────────────────────── │
│  @suhail     Working on  02-26   │ Just shipped a new feature! 🚀   │
│  @user       Retweeted    02-25  │ This is a long tweet content...  │
├──────────────────────────────────┴──────────────────────────────────┤
│ Q:退出  R:刷新  Space:暂停  ↑↓:选择  ←→:翻页  g/G:首尾              │
│ /:搜索  u:用户过滤  o:打开URL  Alt+↑↓:滚动详情  Alt+R:重载配置    │
└─────────────────────────────────────────────────────────────────────┘
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
| `→` / `PageDown` | Next page |
| `←` / `PageUp` | Previous page |
| `G` | Jump to bottom |
| `g` | Jump to top |
| `/` | Keyword search/filter |
| `u` | Toggle filter by current user |
| `o` | Open tweet URL in browser |
| `Alt+↓` | Scroll details panel down |
| `Alt+↑` | Scroll details panel up |
| `Alt+R` / `F5` | Reload configuration |

## Configuration

Create a `config.toml` file:

```toml
[general]
poll_interval_sec = 300
nitter_instance = "https://nitter.net"
max_tweets = 400
filter_replies = true
persist_state = true
max_saved_tweets = 1000
incremental_save = true
merge_threshold = 50

[users]
handles = ["karpathy", "dotey", "op7418", "chengfeng240928", "bcherny", "lijigang", "123olp", "AI_Whisper_X", "vista8"]

[notification]
enable = true
sound = true
flash = true
desktop = false
title_badge = true     # 窗口标题显示未读数 + macOS Dock 徽章
burst_threshold = 5    # 爆发检测阈值（推文数/分钟）
burst_window_sec = 60  # 爆发检测时间窗口（秒）
burst_sound = true     # 爆发时连响三声

[ui]
theme = "dark"
show_timestamps = true
auto_scroll = true
```

### Configuration Options

- `poll_interval_sec`: How often to check for new tweets (min: 10)
- `nitter_instance`: Which Nitter mirror to use
- `max_tweets`: Maximum tweets to keep in memory
- `filter_replies`: Filter out reply tweets (true = show only original tweets and retweets)
- `persist_state`: Enable state persistence between sessions
- `max_saved_tweets`: Maximum tweets to save to disk
- `incremental_save`: Enable incremental save mode (only new tweets are written)
- `merge_threshold`: Merge incremental file after this many new tweets
- `handles`: List of Twitter usernames (without @)
- `enable`: Enable notifications
- `sound`: Terminal bell on new tweets
- `flash`: Visual alert on new tweets (non-blocking)
- `title_badge`: Show unread count in window title and macOS Dock badge
- `burst_threshold`: Number of tweets within the window that triggers burst mode
- `burst_window_sec`: Time window for burst detection (seconds)
- `burst_sound`: Ring bell 3× in burst mode instead of once

### State Persistence

x-monitor automatically saves your tweet history to disk. When you restart the app:

- Previously loaded tweets are restored
- Read/unread status (🔔) is correctly preserved across sessions
- History is saved to `~/.config/x-monitor/state.json` (or `./state.json`)

**Incremental Save Mode (默认启用)**:

增量保存模式只保存新增的推文，减少磁盘写入，提高性能：

- 新推文保存到 `state.incremental.json`
- 达到 `merge_threshold` 条时自动合并到主文件
- 退出时强制合并，确保不丢失数据
- 启动时自动应用增量文件

文件结构：
```
~/.config/x-monitor/
├── state.json              # 主文件：完整推文列表
└── state.incremental.json  # 增量文件：新增推文（自动清理）
```

如需使用传统全量保存模式，设置 `incremental_save = false`。

You can disable state persistence by setting `persist_state = false` in your config.

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
│   ├── config.py        # TOML configuration
│   ├── types.py         # Data structures
│   ├── fetcher.py       # RSS fetching (feedparser + httpx)
│   ├── monitor.py       # Polling logic (asyncio)
│   ├── notifier.py      # Notifications (bell, flash, title badge, burst detection)
│   ├── state_manager.py # State persistence
│   └── ui.py            # TUI (prompt_toolkit)
├── config.toml
├── main.py
├── pyproject.toml
└── README.md
```

## License

MIT
