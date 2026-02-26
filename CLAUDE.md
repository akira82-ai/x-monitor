# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

x-monitor 是一个基于 TUI 的 Twitter 用户监控 CLI 工具，通过 Nitter RSS feeds 获取推文，使用 prompt_toolkit 构建界面。

## 开发命令

```bash
# 安装依赖
make install
# 或
python3 -m venv .venv
.venv/bin/pip install -q prompt_toolkit feedparser httpx toml wcwidth

# 创建示例配置
make config
# 或
.venv/bin/python3 main.py --create-config

# 运行应用
make run
# 或
.venv/bin/python3 main.py

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
                    ↓                      ↓
              StateManager (持久化)    StateManager (加载)
```

### 关键组件

1. **AppState (`src/types.py`)** - 应用状态的中心数据类
   - 包含推文列表、分页状态、过滤状态、加载状态等
   - `to_dict()` / `from_dict()` 用于序列化
   - 过滤功能：`filter_keyword`（关键词）、`filter_user`（用户）

2. **TweetFetcher (`src/fetcher.py`)** - RSS 获取和解析
   - 使用 httpx 异步客户端获取 RSS
   - 使用 feedparser 解析 RSS 内容
   - 自动检测转推和回复推文

3. **Monitor (`src/monitor.py`)** - 轮询逻辑协调器
   - `poll_once()` - 执行一次轮询
   - `reload_config()` - 热重载配置文件
   - 管理新推文通知和推文去重

4. **StateManager (`src/state_manager.py`)** - 状态持久化
   - 保存到 `~/.config/x-monitor/state.json` 或 `./state.json`
   - 自动限制推文数量（max_saved_tweets）

5. **UI (`src/ui.py`)** - prompt_toolkit TUI 界面
   - `TweetTableControl` - 左侧推文列表（支持分页、过滤）
   - `TweetDetailsControl` - 右侧详情面板（支持滚动）
   - `create_key_bindings()` - 快捷键绑定，需要传入 monitor 参数

### 关键快捷键

| 快捷键 | 功能 |
|--------|------|
| `/` | 关键词搜索/过滤 |
| `u` | 切换仅显示当前用户推文 |
| `o` | 在浏览器中打开推文 URL |
| `Ctrl+↓/↑` | 在详情面板内滚动 |
| `Ctrl+R` / `F5` | 热重载配置文件 |

## 配置系统

配置文件 `config.toml` 支持以下结构：

```toml
[general]
poll_interval_sec = 300      # 轮询间隔（秒）
nitter_instance = "https://nitter.net"
max_tweets = 400             # 内存中最大推文数
filter_replies = true        # 过滤回复推文
persist_state = true         # 持久化状态
max_saved_tweets = 1000      # 最大保存推文数

[users]
handles = ["user1", "user2"]  # Twitter 用户名（不带 @）

[notification]
enable = true
sound = true                 # 终端响铃
flash = true                 # 视觉提醒
desktop = false              # 桌面通知
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

## UI 注意事项

- 使用 `wcswidth()` 计算中文字符显示宽度
- 分页状态 `current_page` 基于过滤后的结果
- 详情面板滚动偏移 `details_scroll_offset` 在切换推文时重置为 0
