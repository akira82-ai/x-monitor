"""Smoke tests for the main entrypoint."""

from argparse import Namespace
from unittest.mock import Mock

from src import main as main_module
from src.types import AppState


def test_main_async_create_config(monkeypatch, capsys):
    """`--create-config` should save the default config and exit early."""
    save_mock = Mock()

    monkeypatch.setattr(
        main_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: Namespace(config=None, create_config=True),
    )
    monkeypatch.setattr(main_module.Config, "save", save_mock)

    main_module.asyncio.run(main_module.main_async())

    save_mock.assert_called_once_with("config.toml")
    captured = capsys.readouterr()
    assert "Created config.toml" in captured.out


def test_main_swallows_keyboard_interrupt(monkeypatch):
    """Top-level main() should exit cleanly on Ctrl+C."""
    run_mock = Mock()

    def fake_run(coro):
        run_mock(coro)
        coro.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(main_module.asyncio, "run", fake_run)

    main_module.main()

    run_mock.assert_called_once()


def test_load_initial_state_restores_saved_state_and_resets_page_size(monkeypatch):
    """Loading persisted state should preserve tweets but normalize UI page size."""
    config = main_module.Config()
    tracker = Mock()
    tracker.add_step.side_effect = ["sm", "state"]
    saved_state = AppState(page_size=99)
    saved_state.tweets = [Mock(), Mock()]
    saved_state._clamp_current_page = Mock()
    fake_state_manager = Mock()
    fake_state_manager.load.return_value = saved_state

    monkeypatch.setattr(main_module, "StateManager", Mock(return_value=fake_state_manager))

    state, state_manager = main_module._load_initial_state(config, tracker)

    assert state is saved_state
    assert state_manager is fake_state_manager
    assert state.page_size == 10
    saved_state._clamp_current_page.assert_called_once()
    tracker.complete.assert_any_call("state", "已恢复 2 条推文")


def test_save_state_on_exit_persists_when_enabled(capsys):
    """Shutdown persistence helper should delegate to monitor.save_state()."""
    config = main_module.Config()
    state_manager = Mock()
    monitor = Mock()

    main_module._save_state_on_exit(config, state_manager, monitor)

    monitor.save_state.assert_called_once()
    captured = capsys.readouterr()
    assert "正在保存状态..." in captured.out
