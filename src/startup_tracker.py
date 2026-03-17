"""启动过程追踪器，用于显示启动进度."""

import sys
import time
from typing import Optional
from enum import Enum


class StepStatus(Enum):
    """步骤状态枚举."""
    PENDING = "⏸"
    RUNNING = "⏳"
    SUCCESS = "✓"
    FAILED = "✗"
    WARNING = "?"


class StartupTracker:
    """追踪和显示启动进度."""

    def __init__(self):
        """初始化追踪器."""
        self.steps = []
        self.current_step = None
        self.start_time = None
        self.last_update = None
        self._terminal_height = 0

    def add_step(self, name: str, parent: Optional[str] = None) -> str:
        """添加一个启动步骤.

        Args:
            name: 步骤名称
            parent: 父步骤ID（用于子步骤）

        Returns:
            步骤ID
        """
        step_id = f"step_{len(self.steps)}"
        self.steps.append({
            "id": step_id,
            "name": name,
            "parent": parent,
            "status": StepStatus.PENDING,
            "message": None,
            "start_time": None,
            "end_time": None,
        })
        return step_id

    def start(self, step_id: str, message: Optional[str] = None) -> None:
        """开始执行一个步骤.

        Args:
            step_id: 步骤ID
            message: 可选的进度消息
        """
        if not self.start_time:
            self.start_time = time.time()

        for step in self.steps:
            if step["id"] == step_id:
                step["status"] = StepStatus.RUNNING
                step["start_time"] = time.time()
                step["message"] = message
                self.current_step = step_id
                self._refresh_display()
                break

    def complete(self, step_id: str, message: Optional[str] = None) -> None:
        """标记步骤成功.

        Args:
            step_id: 步骤ID
            message: 可选的完成消息
        """
        for step in self.steps:
            if step["id"] == step_id:
                step["status"] = StepStatus.SUCCESS
                step["end_time"] = time.time()
                if message:
                    step["message"] = message
                self._refresh_display()
                break

    def fail(self, step_id: str, error: str) -> None:
        """标记步骤失败.

        Args:
            step_id: 步骤ID
            error: 错误信息
        """
        for step in self.steps:
            if step["id"] == step_id:
                step["status"] = StepStatus.FAILED
                step["end_time"] = time.time()
                step["message"] = f"错误: {error}"
                self._refresh_display()
                break

    def update(self, step_id: str, message: str) -> None:
        """更新当前步骤的进度信息.

        Args:
            step_id: 步骤ID
            message: 进度消息
        """
        for step in self.steps:
            if step["id"] == step_id:
                step["message"] = message
                self._refresh_display()
                break

    def _refresh_display(self) -> None:
        """刷新显示."""
        # 清屏并重新打印所有步骤
        print("\033[H\033[J", end="")  # 清屏
        print("正在启动 x-monitor...\n")

        for step in self.steps:
            if step["parent"]:
                continue  # 子步骤单独处理

            status_char = step["status"].value
            print(f"[{status_char}] {step['name']}")

            if step["message"]:
                indent = "      " if step["status"] != StepStatus.RUNNING else "   "
                print(f"{indent}{step['message']}")

            # 显示子步骤
            children = [s for s in self.steps if s["parent"] == step["id"]]
            for child in children:
                child_status = child["status"].value
                child_msg = f" - {child['message']}" if child["message"] else ""
                print(f"      [{child_status}] {child['name']}{child_msg}")

        print()  # 空行
        sys.stdout.flush()

    def clear(self) -> None:
        """清除启动显示."""
        print("\033[H\033[J", end="")  # 清屏
        sys.stdout.flush()
