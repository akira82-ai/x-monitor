# x-monitor 真实数据使用指南

## 快速开始

项目已配置好监控三个 Twitter 账号：karpathy、dotey、op7418

```bash
cd /Users/agiray/Desktop/github/x-monitor
./run.sh
```

## 1. 账号管理

### 配置文件位置

按以下优先级查找配置：
1. 命令行指定：`python main.py /path/to/config.toml`
2. 项目根目录：`config.toml` ✅
3. 用户目录：`~/.config/x-monitor/config.toml`
4. 隐藏文件：`.x-monitor.toml`

### 当前配置

```toml
[users]
handles = ["karpathy", "dotey", "op7418"]
```

### 添加/删除账号

编辑 `config.toml`：

```toml
[users]
handles = ["karpathy", "dotey", "op7418", "elonmusk", "sama"]
```

**注意**：
- ✅ 只写用户名：`"karpathy"`
- ❌ 不要加 @：`"@karpathy"`
- 至少需要一个账号
- 修改后需重启应用

### RSS URL 格式

程序自动构建：
```
https://nitter.net/karpathy/rss
https://nitter.net/dotey/rss
https://nitter.net/op7418/rss
```

## 2. 刷新/轮询机制

### 轮询配置

```toml
[general]
poll_interval_sec = 60  # 每 60 秒检查一次
max_tweets = 50         # 每账号最多 50 条推文
```

### 工作流程

**启动时**：
1. 加载配置
2. 立即获取初始数据
3. 启动后台轮询

**后台循环**（每 60 秒）：
```
遍历所有账号
  ├─ 请求 RSS feed
  ├─ 解析推文（ID、时间、内容、URL）
  ├─ 检查新推文（ID 去重）
  ├─ 添加到状态
  ├─ 在网络异常时重建连接 / 必要时切换实例
  ├─ 触发通知
  ├─ 修剪旧推文（超过 max_tweets）
  └─ 刷新 UI
```

### 手动控制

| 按键 | 功能 |
|------|------|
| **R** | 立即刷新 |
| **/** | 搜索/过滤 |
| **u** | 仅显示当前用户 |
| **o** | 打开当前推文 |
| **c** | 复制当前推文 |
| **j/k** | 上下导航 |
| **←/→** | 翻页 |
| **Q** | 退出 |

### 调整轮询间隔

编辑 `config.toml`：

```toml
[general]
poll_interval_sec = 30   # 更频繁
# 或
poll_interval_sec = 300  # 更节省（5 分钟）
```

**限制**：
- 最小值：10 秒
- 推荐值：60-300 秒
- 修改后需重启

### 数据持久化

**当前行为**：
- 推文状态会保存到本地 `state.json`
- 关闭应用后会恢复最近的浏览状态与未读状态
- 启动后会在恢复历史状态基础上继续拉取最新推文

**推文数量限制**：
```toml
[general]
max_tweets = 50  # 每账号最多 50 条
```

总推文数 = 账号数 × max_tweets（当前最多 150 条）

## 3. 使用方法

### 方法 1：直接运行（推荐）

```bash
cd /Users/agiray/Desktop/github/x-monitor
./run.sh
```

或手动：
```bash
source .venv/bin/activate
python3 main.py
```

### 方法 2：指定配置

```bash
python3 main.py /path/to/custom-config.toml
```

### 方法 3：创建新配置

```bash
python3 main.py --create-config
```

## 4. 预期行为

### 启动后

1. **初始加载**：
   - 显示配置信息
   - 立即获取最新推文
   - 可能需要几秒钟

2. **UI 显示**：
   ```
   x-monitor | ▶ • 🔔 X 条新 • N 条 • 1/2 页 • 刚刚
   User             Content                         Date
   ─────────────────────────────────────────────────────
   @karpathy        Tweet content preview...       03-31
   ...
   Q:退出  ↑↓:选择  ←→:翻页  /:搜索  u:用户过滤  o:打开URL  c:复制
   ```

3. **自动更新**：
   - 每 60 秒检查新推文
   - 新推文时显示 "🔔 X new"
   - 可选终端铃声/闪烁

## 5. 故障排查

### 无法获取推文

**检查 Nitter 实例**：
```bash
curl https://nitter.net/karpathy/rss
```

**更换实例**：
```toml
[general]
nitter_instance = "https://nitter.poast.org"
# 其他实例：https://github.com/zedeus/nitter/wiki/Instances
```

### 轮询太慢/太快

调整 `poll_interval_sec`：
- 太慢：减小数值（最小 10）
- 太快：增大数值（推荐 60-300）

### 推文太多/太少

调整 `max_tweets`：
```toml
[general]
max_tweets = 100  # 增加到 100 条
```

## 6. 完整配置示例

```toml
# x-monitor Configuration File

[general]
poll_interval_sec = 60
nitter_instance = "https://nitter.net"
max_tweets = 50

[users]
handles = ["karpathy", "dotey", "op7418"]

[notification]
enable = true
sound = true
flash = true
desktop = false  # 需要 plyer 库

[ui]
theme = "dark"
show_timestamps = true
auto_scroll = true
```

## 7. 关键文件

| 文件 | 功能 |
|------|------|
| `config.toml` | 账号和轮询设置 |
| `main.py` | 入口点 |
| `run.sh` | 快速启动脚本 |
| `src/config.py` | 配置加载和验证 |
| `src/fetcher.py` | RSS 解析 |
| `src/monitor.py` | 后台轮询逻辑 |

## 总结

✅ **账号管理**：编辑 `config.toml` 的 `[users]` 部分

✅ **刷新机制**：
- 自动：每 60 秒（可配置）
- 手动：按 R 键

✅ **当前配置**：
- 监控：karpathy, dotey, op7418
- 间隔：60 秒
- 最大：50 条/账号

✅ **立即使用**：
```bash
cd /Users/agiray/Desktop/github/x-monitor
./run.sh
```
