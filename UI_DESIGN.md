# UI Design Documentation

## Layout Overview

```
┌─────────────────────────────────────────────────────────────┐
│ x-monitor - Twitter User Monitoring                         │ ← Header
├─────────────────────────────────────────────────────────────┤
│ ▶ RUNNING • 📊 25 tweets • 🕐 14:32:15                      │ ← Status Bar
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User         Content                          Time         │
│  ────────────────────────────────────────────────────────   │
│  @karpathy    Just shipped a new feature! 🚀   2h          │
│  @suhail      Working on AI research...        5h          │
│  @dotey       🔁 Coffee + Code = Productivity   1d          │
│                                                              │
│                          Main Content Area                   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ Q: Quit │ R: Refresh │ Space: Pause │ D: Details │ ...     │ ← Keybindings
└─────────────────────────────────────────────────────────────┘
```

## With Details Panel

```
┌─────────────────────────────────────────────────────────────┐
│ x-monitor - Twitter User Monitoring                         │
├─────────────────────────────────────────────────────────────┤
│ ▶ RUNNING • 🔔 3 new • 📊 25 tweets • 🕐 14:32:15          │
├──────────────────────────────────┬──────────────────────────┤
│                                  │                          │
│  User      Content        Time   │  # @karpathy            │
│  ──────────────────────────────  │                          │
│  @karpathy Just shipped... 2h    │  **Posted:** 2024-...   │
│  @suhail   Working on...  5h    │                          │
│  @dotey    🔁 Coffee...    1d    │  ---                     │
│                                  │                          │
│         Tweet List               │  Just shipped a new      │
│                                  │  feature! 🚀             │
│                                  │                          │
│                                  │  ---                     │
│                                  │                          │
│                                  │  **URL:** https://...    │
│                                  │                          │
│                                  │    Details Panel         │
└──────────────────────────────────┴──────────────────────────┘
│ Q: Quit │ R: Refresh │ Space: Pause │ D: Details │ ...     │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Minimal Color Blocks
- **No large background colors** - Only use borders and lines
- **Subtle borders** - Use `solid` borders instead of `thick`
- **Transparent backgrounds** - Let terminal theme show through
- **Accent colors** - Only for borders and highlights

### 2. Clear Visual Hierarchy
- **Header** - Bold title with bottom border
- **Status Bar** - Icons + text with subtle border
- **Main Content** - Clean table with zebra stripes
- **Details Panel** - Side panel with left border
- **Keybindings Bar** - Dimmed text at bottom

### 3. Information Density
- **Icons** - Use emoji for visual cues (▶, ⏸, 🔔, 📊, 🕐, 🔁)
- **Compact layout** - Single-line bars, no wasted space
- **Smart truncation** - Preview text at 80 chars
- **Relative time** - Show "2h" instead of full timestamp

### 4. Keyboard-First Design
- **Always visible shortcuts** - Bottom bar shows all keys
- **Vim-style navigation** - j/k for up/down
- **Quick actions** - Single key for common tasks
- **No mouse required** - Everything accessible via keyboard

## Color Scheme

### Borders
- `$accent` - Main borders (header, details, keybindings)
- `$primary-lighten-1` - Status bar border
- `$primary` - Table header border

### Text
- Default - Main content
- `$text-muted` - Keybindings bar
- `dim` - Less important text

### Highlights
- `$primary 20%` - Selected row (subtle background)
- Zebra stripes - Alternating row colors

## Components

### Header Bar
- **Height**: 1 line
- **Content**: App title
- **Style**: Bold text, bottom border
- **Padding**: 0 2

### Status Bar
- **Height**: 1 line
- **Content**: Status icon, new count, total tweets, last update
- **Style**: Normal text, bottom border
- **Padding**: 0 2
- **Icons**: ▶/⏸ (status), 🔔 (new), 📊 (total), 🕐 (time)

### Tweet List
- **Type**: DataTable
- **Columns**: User, Content, Time
- **Features**: Zebra stripes, cursor highlight
- **Icons**: 🔁 for retweets
- **Padding**: 0 1

### Details Panel
- **Width**: 40% of screen
- **Type**: Markdown
- **Border**: Left border only
- **Content**: Full tweet details
- **Padding**: 1 2
- **Badges**: 🔁 RETWEET, 💬 REPLY

### Keybindings Bar
- **Height**: 1 line
- **Content**: Key shortcuts separated by │
- **Style**: Dimmed, centered
- **Padding**: 0 2
- **Format**: "Key: Action │ Key: Action"

## Responsive Behavior

### Details Panel Toggle
- Press `D` to show/hide details panel
- When hidden: Tweet list uses full width
- When shown: Tweet list 60%, details 40%

### Selection
- Arrow keys or j/k to navigate
- Selected row has subtle background
- Details panel updates automatically

### Status Updates
- Status bar updates every poll interval
- New tweet count shows with 🔔 icon
- Last update time shows current time

## Accessibility

### Visual
- High contrast borders
- Clear text hierarchy
- No reliance on color alone
- Icons supplement text

### Keyboard
- All functions keyboard accessible
- Vim-style shortcuts for power users
- Standard arrow keys also work
- Single-key commands for speed

### Screen Readers
- Semantic structure
- Clear labels
- Status updates
- Descriptive text

## Future Enhancements

### Potential Improvements
- [ ] Color themes (light/dark/custom)
- [ ] Configurable column widths
- [ ] Resizable details panel
- [ ] Search/filter bar
- [ ] Tweet preview images
- [ ] Custom keybindings
- [ ] Status bar customization
- [ ] Multiple color schemes
