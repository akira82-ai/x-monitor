"""Test configuration loading and validation."""

import pytest
import tempfile
from pathlib import Path

from config import Config, GeneralConfig, UsersConfig


class TestGeneralConfig:
    """Test GeneralConfig validation."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GeneralConfig()
        assert config.poll_interval_sec == 300
        assert config.nitter_instance == "https://nitter.net"
        assert config.max_tweets == 50
        assert config.filter_replies is True
        assert config.persist_state is True
        assert config.max_saved_tweets == 1000
        assert config.incremental_save is True
        assert config.merge_threshold == 50
        assert config.auto_merge_interval_sec == 60

    def test_validate_poll_interval_too_low(self):
        """Test validation fails when poll_interval_sec < 10."""
        config = GeneralConfig(poll_interval_sec=5)
        with pytest.raises(ValueError, match="poll_interval_sec must be at least 10 seconds"):
            config.validate()

    def test_validate_poll_interval_valid(self):
        """Test validation passes when poll_interval_sec >= 10."""
        config = GeneralConfig(poll_interval_sec=10)
        config.validate()  # Should not raise

    def test_validate_auto_merge_negative(self):
        """Test validation fails when auto_merge_interval_sec < 0."""
        config = GeneralConfig(auto_merge_interval_sec=-1)
        with pytest.raises(ValueError, match="auto_merge_interval_sec must be non-negative"):
            config.validate()

    def test_validate_auto_merge_zero(self):
        """Test validation passes when auto_merge_interval_sec = 0 (disabled)."""
        config = GeneralConfig(auto_merge_interval_sec=0)
        config.validate()  # Should not raise

    def test_validate_nitter_url_missing_protocol(self):
        """Test URL validation fails when protocol is missing."""
        config = GeneralConfig(nitter_instance="nitter.net")
        with pytest.raises(ValueError, match="nitter_instance must use http or https protocol"):
            config.validate()

    def test_validate_nitter_url_invalid_protocol(self):
        """Test URL validation fails when protocol is not http/https."""
        config = GeneralConfig(nitter_instance="file:///etc/passwd")
        with pytest.raises(ValueError, match="nitter_instance must use http or https protocol"):
            config.validate()

    def test_validate_nitter_url_valid(self):
        """Test URL validation passes for valid URLs."""
        config = GeneralConfig(nitter_instance="https://nitter.net")
        config.validate()  # Should not raise

        config = GeneralConfig(nitter_instance="http://nitter.poast.org")
        config.validate()  # Should not raise


class TestUsersConfig:
    """Test UsersConfig validation."""

    def test_default_empty_handles(self):
        """Test default configuration has no handles."""
        config = UsersConfig()
        assert config.handles == []

    def test_validate_empty_handles(self):
        """Test validation fails when no users specified."""
        config = UsersConfig(handles=[])
        with pytest.raises(ValueError, match="No users specified in configuration"):
            config.validate()

    def test_validate_handle_with_at_symbol(self):
        """Test validation fails when handle includes @ symbol."""
        config = UsersConfig(handles=["@user1"])
        with pytest.raises(ValueError, match="should not include @ symbol"):
            config.validate()

    def test_validate_valid_handles(self):
        """Test validation passes for valid handles."""
        config = UsersConfig(handles=["user1", "user2"])
        config.validate()  # Should not raise


class TestConfig:
    """Test Config loading and saving."""

    def test_load_from_file(self):
        """Test loading configuration from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
[general]
poll_interval_sec = 600
nitter_instance = "https://nitter.poast.org"

[users]
handles = ["user1", "user2"]
""")
            f.flush()
            temp_path = f.name

        try:
            config = Config.load(temp_path)
            assert config.general.poll_interval_sec == 600
            assert config.general.nitter_instance == "https://nitter.poast.org"
            assert config.users.handles == ["user1", "user2"]
        finally:
            Path(temp_path).unlink()

    def test_save_to_file(self):
        """Test saving configuration to file."""
        config = Config()
        config.general.poll_interval_sec = 300
        config.users.handles = ["testuser"]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            temp_path = f.name

        try:
            config.save(temp_path)
            loaded_config = Config.load(temp_path)
            assert loaded_config.general.poll_interval_sec == 300
            assert loaded_config.users.handles == ["testuser"]
        finally:
            Path(temp_path).unlink()
