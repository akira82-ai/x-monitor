"""Smoke tests for the main entrypoint."""

from argparse import Namespace
from unittest.mock import Mock

from src import main as main_module


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
