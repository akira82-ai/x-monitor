"""Search overlay state and prompt-toolkit bindings."""

from datetime import datetime, timezone
from typing import Callable

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import BufferControl

from .config import Config
from .types import AppState


class SearchOverlay:
    """Owns search overlay widgets and their small state machine."""

    def __init__(self, layout_factory: Callable[[AppState, Config], object]):
        self._layout_factory = layout_factory
        self.buffer = Buffer(name="search", multiline=False)
        self._state_ref = [None]
        self._config_ref = [None]
        self.not_searching_filter = Condition(self._not_in_search_mode)

        self._key_bindings = KeyBindings()
        self._register_key_bindings()

        self.control = BufferControl(
            buffer=self.buffer,
            key_bindings=self._key_bindings,
            focusable=True,
        )
        self.window = Window(content=self.control, style="class:search.box")

    def _not_in_search_mode(self) -> bool:
        """Return whether the main UI shortcuts should be active."""
        state = self._state_ref[0]
        return not state.search_visible if state is not None else True

    def attach(self, state: AppState, config: Config) -> None:
        """Bind the overlay to the current app state and config."""
        self.buffer.state = state
        self._state_ref[0] = state
        self._config_ref[0] = config

    @property
    def current_config(self) -> Config:
        """Return the config currently bound to the overlay."""
        return self._config_ref[0]

    def _rebuild_layout(self, app, state: AppState) -> None:
        """Recreate the layout so the float visibility matches current state."""
        config = self._config_ref[0]
        if config is not None:
            app.layout = self._layout_factory(state, config)

    def _resolve_state(self) -> AppState:
        """Resolve the active state from the buffer or fallback reference."""
        state = self.buffer.state
        if state is None:
            state = self._state_ref[0]
        return state

    def _register_key_bindings(self) -> None:
        @self._key_bindings.add("escape")
        def _cancel_search(event):
            state = self._resolve_state()
            if state is None:
                return

            state.search_visible = False
            self.buffer.text = ""
            self._rebuild_layout(event.app, state)
            event.app.invalidate()

        @self._key_bindings.add("enter")
        def _confirm_search(event):
            state = self._resolve_state()
            if state is None:
                return

            keyword = self.buffer.text.strip()
            if keyword:
                state.apply_keyword_filter(keyword)
                state.status_message = f"关键词: {keyword}"
                state.status_message_timestamp = datetime.now(timezone.utc)
            else:
                state.clear_filters()
                state.status_message = "已清除过滤"
                state.status_message_timestamp = datetime.now(timezone.utc)

            state.search_visible = False
            self._rebuild_layout(event.app, state)
            event.app.invalidate()
