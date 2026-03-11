#!/usr/bin/env python3
"""测试通知修复的验证脚本。

运行此脚本可以验证通知机制是否正常工作：

1. 应用启动时恢复未读状态
2. 运行时收到新推文的通知
3. 用户已读后清除徽章
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.notifier import Notifier
from src.types import AppState, Tweet
from datetime import datetime, timezone
from src.config import Config


def test_scenario_1():
    """测试场景 1: 应用启动时恢复未读状态"""
    print("=" * 60)
    print("场景 1: 应用启动时恢复未读状态")
    print("=" * 60)

    state = AppState()

    # 手动添加 5 条未读推文
    for i in range(5):
        tweet = Tweet(
            id=f"test_{i}",
            author="testuser",
            author_name="Test User",
            content=f"Test tweet {i}",
            timestamp=datetime.now(timezone.utc),
            url=f"https://x.com/testuser/status/test_{i}",
            is_new=True,
        )
        state.tweets.append(tweet)

    state.new_tweets_count = 5
    print(f"✓ 创建了 {state.new_tweets_count} 条未读推文")

    # 初始化 Notifier
    config = Config()
    config.notification.enable = True
    config.notification.title_badge = True
    notifier = Notifier(config)

    # 恢复通知状态（关键测试：new_count=0）
    print("✓ 调用 notify_batch(0, 5) 恢复通知状态...")
    notifier.notify_batch(0, state.new_tweets_count)

    print("✅ 如果窗口标题显示 '[🔔5] x-monitor'，则测试通过！")
    print()
    return True


def test_scenario_2():
    """测试场景 2: 运行时收到新推文"""
    print("=" * 60)
    print("场景 2: 运行时收到新推文")
    print("=" * 60)

    state = AppState()

    # 先有 5 条未读推文
    for i in range(5):
        tweet = Tweet(
            id=f"test_{i}",
            author="testuser",
            author_name="Test User",
            content=f"Test tweet {i}",
            timestamp=datetime.now(timezone.utc),
            url=f"https://x.com/testuser/status/test_{i}",
            is_new=True,
        )
        state.tweets.append(tweet)

    state.new_tweets_count = 5

    config = Config()
    config.notification.enable = True
    config.notification.title_badge = True
    config.notification.sound = True
    config.notification.flash = True
    notifier = Notifier(config)

    # 初始状态
    notifier.notify_batch(0, 5)
    print("✓ 初始状态: 5 条未读推文")

    # 收到 2 条新推文
    for i in range(2):
        tweet = Tweet(
            id=f"new_{i}",
            author="testuser",
            author_name="Test User",
            content=f"New tweet {i}",
            timestamp=datetime.now(timezone.utc),
            url=f"https://x.com/testuser/status/new_{i}",
            is_new=True,
        )
        state.tweets.insert(0, tweet)

    state.new_tweets_count = 7
    print("✓ 收到 2 条新推文")

    # 处理新推文（关键测试：new_count>0）
    print("✓ 调用 notify_batch(2, 7) 处理新推文...")
    notifier.notify_batch(2, state.new_tweets_count)

    print("✅ 如果听到响铃声 + 窗口标题显示 '[🔔7] x-monitor'，则测试通过！")
    print()
    return True


def test_scenario_3():
    """测试场景 3: 用户已读后清除徽章"""
    print("=" * 60)
    print("场景 3: 用户已读后清除徽章")
    print("=" * 60)

    state = AppState()

    # 创建 3 条未读推文
    for i in range(3):
        tweet = Tweet(
            id=f"test_{i}",
            author="testuser",
            author_name="Test User",
            content=f"Test tweet {i}",
            timestamp=datetime.now(timezone.utc),
            url=f"https://x.com/testuser/status/test_{i}",
            is_new=True,
        )
        state.tweets.append(tweet)

    state.new_tweets_count = 3

    config = Config()
    config.notification.enable = True
    config.notification.title_badge = True
    notifier = Notifier(config)

    # 显示未读状态
    notifier.notify_batch(0, 3)
    print("✓ 显示未读状态: 3 条未读推文")

    # 用户已读
    state.new_tweets_count = 0
    for tweet in state.tweets:
        tweet.is_new = False
    print("✓ 用户已读所有推文")

    # 清除徽章
    print("✓ 调用 clear_badge() 清除徽章...")
    notifier.clear_badge()

    print("✅ 如果窗口标题恢复为 'x-monitor'，Dock 徽章消失，则测试通过！")
    print()
    return True


def main():
    """运行所有测试场景"""
    print("\n" + "=" * 60)
    print("通知修复验证测试")
    print("=" * 60)
    print()

    all_passed = True

    try:
        all_passed &= test_scenario_1()
    except Exception as e:
        print(f"❌ 场景 1 失败: {e}")
        all_passed = False

    try:
        all_passed &= test_scenario_2()
    except Exception as e:
        print(f"❌ 场景 2 失败: {e}")
        all_passed = False

    try:
        all_passed &= test_scenario_3()
    except Exception as e:
        print(f"❌ 场景 3 失败: {e}")
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("🎉 所有测试场景执行成功！")
        print()
        print("请检查以下内容确认修复有效：")
        print("1. 场景 1: 窗口标题显示 '[🔔5] x-monitor'")
        print("2. 场景 2: 听到响铃声 + 窗口标题显示 '[🔔7] x-monitor'")
        print("3. 场景 3: 窗口标题恢复为 'x-monitor'")
    else:
        print("❌ 部分测试场景失败，请检查错误信息")
    print("=" * 60)


if __name__ == "__main__":
    main()
