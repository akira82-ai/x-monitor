"""Lightweight overlay for adding a monitored user from the TUI."""

from __future__ import annotations

from datetime import datetime, timezone

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.widgets import Frame

from .subscription_actions import SubscriptionActions, validate_handle


class AddUserOverlay:
    """Owns the transient add-user input flow."""

    def __init__(self, actions: SubscriptionActions):
        self.actions = actions
        self.state = actions.state
        self.config = actions.config
        self.buffer = Buffer(name="add-user", multiline=False)
        self.error_message = ""
        self._previous_focus = None
        self._key_bindings = KeyBindings()
        self._register_key_bindings()

        self.control = BufferControl(
            buffer=self.buffer,
            key_bindings=self._key_bindings,
            focusable=True,
        )
        self.visible_filter = Condition(lambda: self.state.ui.add_user_visible)
        self.main_bindings_filter = Condition(lambda: not self.state.ui.add_user_visible)

        body = HSplit(
            [
                Window(
                    content=FormattedTextControl(lambda: " 输入 X 账号名"),
                    height=D.exact(1),
                    style="class:add_user.title",
                ),
                Window(
                    content=FormattedTextControl(lambda: " 例如: dotey 或 @dotey"),
                    height=D.exact(1),
                    style="class:add_user.help",
                ),
                Window(height=D.exact(1), char=" "),
                Window(
                    content=self.control,
                    height=D.exact(1),
                    style="class:add_user.input",
                ),
                Window(height=D.exact(1), char=" "),
                Window(
                    content=FormattedTextControl(self._get_feedback_line),
                    height=D.exact(1),
                    style="class:add_user.error",
                ),
                Window(
                    content=FormattedTextControl(lambda: " Enter 确认  Esc 取消"),
                    height=D.exact(1),
                    style="class:add_user.help",
                ),
            ],
            padding=0,
        )
        self.container = Frame(body=body, title="+ Add user", style="class:add_user.frame")

    def _get_feedback_line(self):
        if self.error_message:
            return self.error_message
        return ""

    def open(self, app=None) -> None:
        """Show the overlay and focus its input."""
        self.error_message = ""
        self.buffer.text = ""
        self.state.ui.add_user_visible = True

        if app is not None and getattr(app, "layout", None) is not None:
            self._previous_focus = getattr(app.layout, "current_window", None)
            try:
                app.layout.focus(self.control)
            except Exception:
                pass
            app.invalidate()

    def close(self, app=None) -> None:
        """Hide the overlay and restore the previous focus when possible."""
        self.error_message = ""
        self.buffer.text = ""
        self.state.ui.add_user_visible = False

        if app is not None and getattr(app, "layout", None) is not None:
            if self._previous_focus is not None:
                try:
                    app.layout.focus(self._previous_focus)
                except Exception:
                    pass
            app.invalidate()

    async def _submit(self, handle: str, app) -> None:
        try:
            await self.actions.add_handle(handle)
        except Exception as exc:
            self.state.set_error(str(exc), datetime.now(timezone.utc))
        finally:
            if app is not None:
                app.invalidate()

    def _register_key_bindings(self) -> None:
        @self._key_bindings.add("escape")
        def _cancel(event):
            self.close(event.app)

        @self._key_bindings.add("enter")
        def _submit(event):
            try:
                handle = validate_handle(self.buffer.text, self.config.users.handles)
            except ValueError as exc:
                self.error_message = str(exc)
                event.app.invalidate()
                return

            self.close(event.app)
            event.app.create_background_task(self._submit(handle, event.app))
