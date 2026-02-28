# x-monitor

在终端中优雅地监控 Twitter 用户——无需 API 密钥，零打扰获取实时动态。

```
┌──────────────────────────────────┬──────────────────────────────────┐
│ x-monitor | ▶ • 🔔 4 条新 • 50 条 │ @karpathy                        │
│ • 1/2 页 • 34秒前                 │ 🔁 转推                          │
├──────────────────────────────────┤ 发布时间: 2025-02-26 10:30:00    │
│  User         Content    Date    │ URL: https://x.com/karpathy/...  │
│  @karpathy   Just shipped  02-26 │ ──────────────────────────────── │
│▶ @suhail     Working on  02-26   │ Just shipped a new feature! 🚀   │
│  @user       Retweeted    02-25  │ This is the tweet content...     │
├──────────────────────────────────┴──────────────────────────────────┤
│ q:退出  r:刷新  Space:暂停  ↑↓:选择  ←→:翻页  /:搜索  o:打开URL    │
└─────────────────────────────────────────────────────────────────────┘
```

## 特点

- 🎯 **多用户统一监控** — 在一个时间线追踪多个账号，告别频繁切换
- 🔔 **智能通知系统** — 爆发检测 + macOS Dock 徽章，重要动态不错过
- 🔍 **强大过滤功能** — 过滤回复、关键词搜索、按用户专注浏览
- 💾 **状态持久化** — 增量保存机制，重启后恢复浏览进度和已读状态
- ⚡ **零门槛使用** — 基于公开 Nitter RSS，无需申请 Twitter API

## 安装

**环境要求：** Python 3.10+

```bash
git clone https://github.com/yourusername/x-monitor.git
cd x-monitor

# 一键启动（自动创建虚拟环境并安装依赖）
./run.sh
```

或手动安装：

```bash
python3 -m venv .venv
.venv/bin/pip install prompt_toolkit feedparser httpx toml wcwidth
```

## 快速开始

```bash
# 1. 生成默认配置文件
.venv/bin/python3 main.py --create-config

# 2. 编辑 config.toml，填入你要监控的用户
[users]
handles = ["karpathy", "sama", "naval"]

# 3. 启动
.venv/bin/python3 main.py
# 或
make run
```

**试用演示模式**（无需网络）：

```bash
./demo.sh
```

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `↑` / `↓` 或 `k` / `j` | 选择上/下一条推文 |
| `←` / `→` 或 `PgUp` / `PgDn` | 上/下一页 |
| `g` / `G` | 跳到第一/最后一条 |
| `Space` | 暂停/恢复自动轮询 |
| `r` | 立即刷新 |
| `/` | 关键词搜索/过滤 |
| `u` | 切换仅显示当前用户推文 |
| `o` | 在浏览器中打开推文 |
| `Alt+↑` / `Alt+↓` | 滚动详情面板 |
| `Alt+R` / `F5` | 热重载配置文件 |
| `q` / `Ctrl+C` | 退出 |

## 配置

完整配置示例（`config.toml`）：

```toml
[general]
poll_interval_sec = 300      # 轮询间隔（秒，最小 10）
nitter_instance = "https://nitter.net"
max_tweets = 400
filter_replies = true        # 过滤回复，只看原创推文和转推
persist_state = true
max_saved_tweets = 1000
incremental_save = true

[users]
handles = ["karpathy", "sama", "naval"]

[notification]
enable = true
sound = true                 # 终端响铃
title_badge = true           # 窗口标题未读数 + macOS Dock 徽章
burst_threshold = 5          # 1 分钟内超过 5 条推文触发爆发提醒
burst_sound = true           # 爆发时连续三声响铃

[ui]
theme = "dark"
show_timestamps = true
```

## Nitter 实例

如果 `nitter.net` 不可用，可在配置中更换其他镜像：

```toml
nitter_instance = "https://nitter.poast.org"
```

可用镜像列表：[Nitter Wiki](https://github.com/zedeus/nitter/wiki/Instances)

## 故障排除

**没有推文显示？**
- 在浏览器中检查 Nitter 实例是否可访问
- 更换其他 Nitter 镜像
- 等待几分钟（可能触发了速率限制）

**需要使用代理？**
- 设置系统环境变量 `https_proxy` 或 `http_proxy`（仅支持 HTTP/HTTPS）

**运行测试：**

```bash
.venv/bin/python3 test.py
```

## License

MIT
