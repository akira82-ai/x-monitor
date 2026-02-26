# x-monitor Project Overview

## Project Structure

```
x-monitor-python/
├── src/
│   ├── __init__.py         # Package initialization
│   ├── config.py           # Configuration management (TOML)
│   ├── types.py            # Data structures (Tweet, AppState)
│   ├── fetcher.py          # RSS feed fetching (httpx + feedparser)
│   ├── monitor.py          # Polling logic (asyncio)
│   ├── notifier.py         # Notification system
│   └── ui.py               # TUI interface (Textual)
├── config.toml             # User configuration
├── main.py                 # Entry point
├── test.py                 # Test suite
├── run.sh                  # Startup script
├── Makefile                # Build automation
├── pyproject.toml          # Python project metadata
├── README.md               # User documentation
└── .gitignore              # Git ignore rules
```

## Component Details

### Core Components

1. **config.py** - Configuration Management
   - Loads and validates TOML configuration
   - Provides default values
   - Handles configuration errors

2. **types.py** - Data Structures
   - `Tweet`: Represents a single tweet with metadata
   - `AppState`: Application state management
   - Helper methods for state manipulation

3. **fetcher.py** - RSS Feed Fetcher
   - Fetches tweets via Nitter RSS feeds
   - Parses RSS XML into Tweet objects
   - Handles network errors gracefully
   - Strips HTML from content

4. **monitor.py** - Monitoring Logic
   - Coordinates polling across multiple users
   - Manages background polling task
   - Integrates with notifier
   - Handles state updates

5. **notifier.py** - Notification System
   - Terminal bell notifications
   - Visual flash alerts
   - Optional desktop notifications (via plyer)

6. **ui.py** - Terminal User Interface
   - Built with Textual framework
   - Real-time tweet display
   - Keyboard navigation
   - Status panel
   - Details view

### Data Flow

```
User Config (config.toml)
    ↓
Monitor (monitor.py)
    ↓
Fetcher (fetcher.py) → Nitter RSS
    ↓
Parse RSS → Tweet objects
    ↓
AppState (types.py)
    ↓
UI (ui.py) + Notifier (notifier.py)
    ↓
User Display
```

## Key Features

### 1. Asynchronous Architecture
- Uses `asyncio` for non-blocking I/O
- Concurrent fetching of multiple users
- Background polling without blocking UI

### 2. State Management
- Centralized state in `AppState`
- Deduplication via tweet IDs
- Automatic trimming to max_tweets limit

### 3. Error Handling
- Graceful degradation on network errors
- Per-user error isolation
- User-friendly error messages

### 4. Configuration
- TOML-based configuration
- Sensible defaults
- Easy customization

### 5. User Interface
- Full-screen TUI with Textual
- Vim-style keybindings
- Real-time updates
- Responsive design

## Technical Decisions

### Why Nitter RSS?
- No API keys required
- Simple RSS format
- Public access
- Multiple instances available

### Why Textual?
- Modern TUI framework
- Async-first design
- Rich widget library
- Good documentation

### Why httpx?
- Async HTTP client
- Better than requests for async
- Good error handling
- Modern API

### Why feedparser?
- Battle-tested RSS parser
- Handles malformed feeds
- Simple API
- Wide format support

## Configuration Options

### [general]
- `poll_interval_sec`: Polling frequency (min: 10)
- `nitter_instance`: Nitter mirror URL
- `max_tweets`: Memory limit for tweets

### [users]
- `handles`: List of Twitter usernames

### [notification]
- `enable`: Master notification toggle
- `sound`: Terminal bell
- `flash`: Visual alert
- `desktop`: Desktop notifications (requires plyer)

### [ui]
- `theme`: Color theme
- `show_timestamps`: Display tweet times
- `auto_scroll`: Auto-scroll to new tweets

## Development

### Adding New Features

1. **New data fields**: Update `types.py`
2. **New config options**: Update `config.py`
3. **New UI elements**: Update `ui.py`
4. **New notification types**: Update `notifier.py`

### Testing

Run the test suite:
```bash
python test.py
```

### Debugging

Enable verbose logging by modifying print statements in:
- `fetcher.py`: Network requests
- `monitor.py`: Polling logic
- `ui.py`: UI events

## Future Enhancements

### Potential Features
- [ ] Export tweets to JSON/CSV
- [ ] Search/filter functionality
- [ ] Tweet threading detection
- [ ] Media preview support
- [ ] Multiple Nitter instance fallback
- [ ] Persistent storage (SQLite)
- [ ] Web dashboard option
- [ ] Keyword alerts
- [ ] User statistics
- [ ] Rate limit handling

### Performance Optimizations
- [ ] Connection pooling
- [ ] Caching layer
- [ ] Incremental updates
- [ ] Lazy loading

## Dependencies

### Core
- `textual>=0.80.0`: TUI framework
- `feedparser>=6.0.10`: RSS parsing
- `httpx>=0.27.0`: Async HTTP client
- `toml>=0.10.2`: TOML parsing

### Optional
- `plyer`: Desktop notifications

## License

MIT License - See LICENSE file for details
