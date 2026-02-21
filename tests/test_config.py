# ABOUTME: Tests for configuration loading, defaults, and validation.
# ABOUTME: Covers TOML config reading, default values, and config creation.

import os
import tempfile
from pathlib import Path

from booklore_enrich.config import Config, load_config, save_config, DEFAULT_CONFIG


def test_default_config_has_required_sections():
    config = Config()
    assert config.booklore_url == "http://192.168.7.21:6060"
    assert config.booklore_username == ""
    assert config.rate_limit_seconds == 3
    assert config.headless is True


def test_load_config_from_toml(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[booklore]
url = "http://10.0.0.1:9090"
username = "testuser"

[scraping]
rate_limit_seconds = 5
headless = false

[discovery]
romance_tropes = ["slow-burn"]
scifi_tropes = ["cyberpunk"]
fantasy_tropes = ["dark-fantasy"]
''')
    config = load_config(config_file)
    assert config.booklore_url == "http://10.0.0.1:9090"
    assert config.booklore_username == "testuser"
    assert config.rate_limit_seconds == 5
    assert config.headless is False
    assert config.romance_tropes == ["slow-burn"]
    assert config.scifi_tropes == ["cyberpunk"]
    assert config.fantasy_tropes == ["dark-fantasy"]


def test_load_config_missing_file_returns_defaults(tmp_path):
    config = load_config(tmp_path / "nonexistent.toml")
    assert config.booklore_url == "http://192.168.7.21:6060"


def test_save_config_creates_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config = Config(booklore_url="http://mynas:6060", booklore_username="dylan")
    save_config(config, config_file)
    assert config_file.exists()
    loaded = load_config(config_file)
    assert loaded.booklore_url == "http://mynas:6060"
    assert loaded.booklore_username == "dylan"
