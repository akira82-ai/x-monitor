# Changelog

All notable changes to x-monitor will be documented in this file.

## [0.2.4] - 2026-03-30

### Maintenance
- Simplified state persistence by removing the old incremental save flow
- Updated tests to match the current package layout and tweet expiry behavior
- Aligned documentation with the prompt_toolkit-based UI

## [0.2.1] - 2026-02-25

### UI Visibility Improvements
- Fixed column widths (User: 15, Time: 8, Content: auto)
- Increased content preview from 80 to 100 characters
- Made keybindings bar more visible (removed dim style)
- Added background colors to header, status, and keybindings bars
- Changed keybinding format to `[Key] Action` for clarity
- Improved visual separation between sections

### Bug Fixes
- Ensured header, status, and keybindings bars are always visible
- Fixed content truncation issues
- Better column width distribution

## [0.2.0] - 2026-02-25

### UI Improvements
- Added bottom keybindings bar showing all keyboard shortcuts
- Replaced large color blocks with clean borders and lines
- Improved status bar with icons (▶/⏸, 🔔, 📊, 🕐)
- Added retweet indicator (🔁) in tweet list
- Redesigned details panel with better formatting
- Improved visual hierarchy with subtle borders
- Made DataTable header transparent with border
- Added 40% width details panel with left border
- Removed URL column from main list (available in details)
- Increased content preview to 80 characters

### Design Changes
- Minimal color usage - only borders and highlights
- Transparent backgrounds to respect terminal theme
- Dimmed keybindings bar for less distraction
- Better padding and spacing throughout
- Cleaner, more professional appearance

### Documentation
- Added UI_DESIGN.md with detailed design documentation
- Updated README with UI preview
- Added visual layout diagrams

## [0.1.0] - 2026-02-25

### Initial Release
- RSS feed fetching via Nitter
- Real-time tweet monitoring
- TUI interface with prompt_toolkit
- Multiple user support
- Notification system (bell, flash, desktop)
- Configurable polling interval
- TOML configuration
- Async architecture
- Demo mode for testing
- Comprehensive documentation
- Test suite
- Build automation (Makefile, run.sh)

### Features
- Monitor multiple Twitter users
- No API keys required
- Vim-style keyboard navigation
- Pause/resume monitoring
- Tweet details panel
- Status bar with live updates
- Keyboard shortcuts
- Error handling
- Rate limit awareness

### Documentation
- README.md - User guide
- QUICKSTART.md - Quick start guide
- OVERVIEW.md - Technical overview
- PROJECT.md - Project summary
- LICENSE - MIT License
