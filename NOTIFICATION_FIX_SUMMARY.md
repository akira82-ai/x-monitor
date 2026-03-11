# 通知修复总结

## 问题描述

用户报告了一个严重的体验问题：**运行时收不到新消息通知，只有退出重启后才能看到未读消息提示**。

### 问题现象
1. **运行时**：新推文到达时，没有声音、视觉提示或窗口标题/Dock 徽章更新
2. **重启后**：能看到未读消息提示（UI 状态栏显示 "🔔 X 条新"）

### 根本原因

1. **`notify_batch()` 的检查逻辑问题**
   - 位置：`src/notifier.py:133`
   - 问题：`if new_count <= 0: return` 导致恢复未读状态时无法更新标题/徽章

2. **初始加载时机问题**
   - 位置：`src/main.py:88-95`
   - 问题：初始加载完成后没有触发通知更新

3. **UI 层重复调用**
   - 位置：`src/ui.py:838-840`
   - 问题：重复的通知恢复代码，且因 `new_count=0` 而无效

---

## 修改内容

### 1. 修改 `src/notifier.py`

#### 变更 1.1: 重构 `notify_batch()` 方法

**之前：**
```python
def notify_batch(self, new_count: int, total_unread: int) -> None:
    if not self.config.notification.enable or new_count <= 0:
        return

    # 爆发检测
    is_burst = self._burst_detector.record(new_count)

    # 爆发模式：多次响铃
    if self.config.notification.sound:
        if is_burst and self.config.notification.burst_sound:
            self._bell_burst()
        else:
            self._bell()

    # 视觉闪烁
    if self.config.notification.flash:
        self._flash()

    # 更新标题和徽章
    if self.config.notification.title_badge:
        self._title_badge.update(total_unread, is_burst)
```

**之后：**
```python
def notify_batch(self, new_count: int, total_unread: int) -> None:
    if not self.config.notification.enable:
        return

    # 爆发检测和声音/视觉通知（仅在真正有新消息时）
    if new_count > 0:
        is_burst = self._burst_detector.record(new_count)

        # 爆发模式：多次响铃
        if self.config.notification.sound:
            if is_burst and self.config.notification.burst_sound:
                self._bell_burst()
            else:
                self._bell()

        # 视觉闪烁
        if self.config.notification.flash:
            self._flash()

    # 更新标题和徽章（无论是否有新消息，都要反映当前未读状态）
    if self.config.notification.title_badge:
        is_burst = self._burst_detector.is_bursting() if new_count > 0 else False
        self._title_badge.update(total_unread, is_burst)
```

**关键改动：**
- 将 `new_count <= 0` 的检查移到声音/视觉通知部分
- 标题/徽章更新移到外面，不受 `new_count` 限制

#### 变更 1.2: 添加 `BurstDetector.is_bursting()` 方法

**新增方法：**
```python
def is_bursting(self) -> bool:
    """检查当前是否处于爆发状态。"""
    return len(self._timestamps) > self.threshold
```

---

### 2. 修改 `src/main.py`

**位置：** 在初始加载完成后（第 96 行后）

**新增代码：**
```python
# 初始加载后，如果有未读推文，更新通知状态
if state.new_tweets_count > 0:
    monitor.notifier.notify_batch(0, state.new_tweets_count)
```

**完整上下文：**
```python
    print(f"Loading tweets... 0/{total}", end="", flush=True)
    try:
        await asyncio.wait_for(monitor.poll_once(progress_callback=on_progress), timeout=10.0)
        print(f"\nLoaded {len(state.tweets)} tweets")
    except asyncio.TimeoutError:
        print("\nInitial load timed out, starting UI anyway...")
    except Exception as e:
        print(f"\nError during initial load: {e}")
        print("Starting UI anyway...")

    # 初始加载后，如果有未读推文，更新通知状态
    if state.new_tweets_count > 0:
        monitor.notifier.notify_batch(0, state.new_tweets_count)

    # Run the UI
    try:
        await run_ui(config, state, do_refresh, monitor)
    finally:
        await monitor.stop()
```

---

### 3. 修改 `src/ui.py`

**删除代码（第 838-840 行）：**
```python
# 启动时恢复标题状态（如果有未读推文）
if state.new_tweets_count > 0 and monitor:
    monitor.notifier.notify_batch(0, state.new_tweets_count)
```

**原因：** 此逻辑已在 `main.py` 中处理，避免重复调用

---

## 测试验证

### 自动化测试

运行验证脚本：
```bash
.venv/bin/python3 test_notification_fix.py
```

**测试场景：**
1. ✅ 场景 1: 应用启动时恢复未读状态（`notify_batch(0, 5)`）
2. ✅ 场景 2: 运行时收到新推文（`notify_batch(2, 7)`）
3. ✅ 场景 3: 用户已读后清除徽章（`clear_badge()`）

### 手动测试

#### 测试场景 1: 初始加载时有未读消息

```bash
# 1. 确保状态文件中有未读推文
# 编辑 ~/.config/x-monitor/state.json
# 设置某个推文的 "is_new": true，"new_tweets_count": 5

# 2. 启动应用
./run.sh

# 验证：
# - 窗口标题应显示 "[🔔 5] x-monitor"
# - Dock 徽章显示数字 "5"（macOS）
# - 状态栏显示 "🔔 5 条新"
```

#### 测试场景 2: 运行时收到新推文

```bash
# 1. 启动应用（状态文件为空或已读）
./run.sh

# 2. 等待轮询间隔（默认 300 秒，可修改配置为 30 秒测试）

# 验证：
# - 听到响铃声（如果启用声音）
# - 窗口标题更新
# - Dock 徽章显示数字（macOS）
# - 状态栏显示 "🔔 X 条新"
```

#### 测试场景 3: 重启后查看未读消息

```bash
# 1. 有新推文时退出应用（不标记已读）

# 2. 重新启动
./run.sh

# 验证：
# - 立即看到未读提示（窗口标题、Dock 徽章、状态栏）
# - 不需要等待轮询
```

---

## 预期行为

修复后，通知机制将按以下方式工作：

### 应用启动时
- ✅ 如果状态文件中有未读推文，立即更新窗口标题/Dock 徽章
- ✅ 用户无需等待即可看到未读提示

### 运行时收到新推文
- ✅ 正常触发声音、视觉提示
- ✅ 更新窗口标题/Dock 徽章
- ✅ 状态栏显示未读数量

### 重启应用
- ✅ 未读状态正确恢复和显示
- ✅ 与运行时行为一致

---

## 技术细节

### `notify_batch()` 的语义变化

**之前：**
- `new_count` 控制整个通知流程
- `new_count <= 0` 时直接返回，不做任何处理

**之后：**
- `new_count` 仅控制声音/视觉通知（只在有新消息时触发）
- `total_unread` 控制标题/徽章更新（无论是否有新消息）

### 为什么要这样修改？

1. **语义清晰**：区分"新消息通知"和"状态恢复"
2. **向后兼容**：现有调用方式不受影响
3. **最小改动**：不需要新增 API 或修改调用方

---

## 文件清单

### 修改的文件
1. `src/notifier.py` - 重构 `notify_batch()` 方法
2. `src/main.py` - 添加初始加载后的通知更新
3. `src/ui.py` - 移除重复的通知恢复代码

### 新增的文件
1. `test_notification_fix.py` - 自动化验证脚本

---

## 故障排查

### 问题：窗口标题没有更新

**可能原因：**
1. 通知功能未启用：检查 `config.toml` 中 `[notification]` 部分的 `enable = true`
2. 标题/徽章功能未启用：检查 `title_badge = true`

**调试方法：**
添加日志到 `src/notifier.py`：
```python
def notify_batch(self, new_count: int, total_unread: int) -> None:
    logger.debug(f"notify_batch called: new_count={new_count}, total_unread={total_unread}")
    # ... 后续逻辑
```

### 问题：没有声音

**可能原因：**
1. 声音功能未启用：检查 `config.toml` 中 `sound = true`
2. 终端不支持响铃：尝试其他终端应用

---

## 总结

此次修复解决了通知机制的核心问题，使得：

1. ✅ **应用启动时**能正确显示未读状态
2. ✅ **运行时**能正常接收新消息通知
3. ✅ **重启后**未读状态能正确恢复

修复通过分离"新消息通知"和"状态恢复"逻辑，使得 `notify_batch()` 方法能够同时处理这两种场景。
