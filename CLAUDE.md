# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

x-monitor 是一个基于 TUI 的 Twitter 用户监控 CLI 工具，通过 Nitter RSS feeds 获取推文，使用 prompt_toolkit 构建界面。要求 Python 3.10+。

## 开发命令

**重要：用户使用 `run.sh` 启动应用，修改依赖时必须同时更新 `run.sh` 和 `Makefile`。**

```bash
# 推荐启动方式（用户偏好）
./run.sh

# 安装依赖
python3 -m venv .venv
.venv/bin/pip install -q prompt_toolkit feedparser httpx toml wcwidth pyperclip

# 创建示例配置
.venv/bin/python3 main.py --create-config

# 其他运行方式
make run
# 或
.venv/bin/python3 main.py
# 或指定配置文件
.venv/bin/python3 main.py path/to/config.toml

# 运行测试
make test
# 或
.venv/bin/python3 test.py

# 演示模式（无需网络，使用假数据）
make demo
# 或
.venv/bin/python3 demo.py
```

## 核心架构

### 数据流
```
Nitter RSS → TweetFetcher → Monitor → AppState → UI (prompt_toolkit)
                    ↓            ↓          ↓
              StateManager   Notifier  StateManager (加载)
              (持久化)     (通知/徽章)
```

### 关键组件

1. **AppState (`src/types.py`)** - 应用状态的中心数据类
   - 包含推文列表、分页状态、过滤状态、加载状态等
   - `to_dict()` / `from_dict()` 用于序列化
   - 过滤功能：`filter_keyword`（关键词）、`filter_user`（用户）
   - `unfiltered_tweets` 保存过滤前的完整列表，不会持久化

2. **TweetFetcher (`src/fetcher.py`)** - RSS 获取和解析
   - 使用 httpx 异步客户端获取 RSS，支持 `https_proxy`/`http_proxy` 环境变量（仅 HTTP/HTTPS，不支持 SOCKS）
   - 使用 feedparser 解析 RSS 内容
   - 自动检测转推（`RT @` 前缀）和回复推文（in-reply-to 字段/内容模式）

3. **Monitor (`src/monitor.py`)** - 轮询逻辑协调器
   - `poll_once()` - 执行一次轮询，支持进度回调
   - `reload_config()` - 热重载配置文件（重建 TweetFetcher 和 Notifier）
   - `cleanup_and_save()` - 退出前合并增量文件并保存
   - 管理新推文通知和推文去重，按时间戳降序排序

4. **StateManager (`src/state_manager.py`)** - 两文件增量持久化
   - 主文件：`~/.config/x-monitor/state.json` 或 `./state.json`
   - 增量文件：`~/.config/x-monitor/state.incremental.json` 或 `./state.incremental.json`
   - `save_incremental()` 追加新推文到增量文件；达到 `merge_threshold` 后自动合并
   - 启动时加载主文件后合并增量文件，清除已应用的增量文件
   - 退出时 `cleanup_and_save()` 强制合并增量文件

5. **Notifier (`src/notifier.py`)** - 通知系统
   - `BurstDetector` - 时间窗口内爆发检测（推文/分钟超过阈值）
   - `TitleBadgeManager` - 通过 ANSI 转义序列设置终端标题，macOS 下通过 AppleScript 设置 Dock 徽章
   - `notify_batch()` - 批量通知：响铃、视觉闪烁、标题/徽章更新
   - 桌面通知需要可选依赖 `plyer`

6. **UI (`src/ui.py`)** - prompt_toolkit TUI 界面
   - `TweetTableControl` - 左侧推文列表（支持分页、过滤，50/50 布局）
   - `TweetDetailsControl` - 右侧详情面板（支持滚动）
   - `create_key_bindings()` - 快捷键绑定，需要传入 monitor 参数

### 关键快捷键

| 快捷键 | 功能 |
|--------|------|
| `↑/↓` 或 `k/j` | 选择上/下一条推文 |
| `←/→` 或 `PgUp/PgDn` | 上/下一页 |
| `g` / `G` | 跳到第一/最后一条 |
| `Space` | 暂停/恢复自动轮询 |
| `r` | 立即刷新 |
| `/` | 关键词搜索/过滤 |
| `u` | 切换仅显示当前用户推文 |
| `o` | 在浏览器中打开推文 URL（x.com） |
| `c` | 复制当前推文详情到剪贴板（Markdown 格式） |
| `Alt+↓/↑` | 在详情面板内滚动 |
| `Alt+R` / `F5` | 热重载配置文件 |
| `q` / `Ctrl+C` | 退出 |

## 配置系统

配置文件搜索顺序：`./config.toml` → `~/.config/x-monitor/config.toml` → `./.x-monitor.toml`

```toml
[general]
poll_interval_sec = 300      # 轮询间隔（秒，最小 10）
nitter_instance = "https://nitter.net"
max_tweets = 400             # 内存中最大推文数
filter_replies = true        # 过滤回复推文
persist_state = true         # 持久化状态
max_saved_tweets = 1000      # 最大保存推文数
incremental_save = true      # 增量保存（推荐）
merge_threshold = 50         # 增量文件达到此数量时合并

[users]
handles = ["user1", "user2"]  # Twitter 用户名（不带 @）

[notification]
enable = true
sound = true                 # 终端响铃
flash = true                 # 视觉提醒
desktop = false              # 桌面通知（需要 plyer）
title_badge = true           # 窗口标题未读数和 Dock 徽章（macOS）
burst_threshold = 5          # 爆发检测阈值（推文/分钟）
burst_window_sec = 60        # 爆发检测时间窗口（秒）
burst_sound = true           # 爆发时连续三声响铃

[ui]
theme = "dark"
show_timestamps = true
auto_scroll = true
```

## Nitter 实例

如果 nitter.net 不可用，可更换为其他镜像：
- https://nitter.poast.org
- https://nitter.privacydev.net
- https://nitter.mint.lgbt

## 状态管理

- `AppState` 的所有修改需要考虑序列化兼容性
- 添加新字段时需要更新 `to_dict()` 和 `from_dict()`
- 过滤状态不影响原始推文列表，仅在 UI 层面过滤
- `unfiltered_tweets` 字段不持久化，重启后过滤状态不会恢复

## UI 注意事项

- 使用 `prompt_toolkit` 的 `get_cwidth()` 计算字符显示宽度（与渲染一致）
- 分页状态 `current_page` 基于过滤后的结果
- 详��面板滚动偏移 `details_scroll_offset` 在切换推文时重置为 0
- 布局为左右各 50%（`term_width // 2`），不支持动态调整
