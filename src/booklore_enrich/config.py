# ABOUTME: Configuration management for booklore-enrich.
# ABOUTME: Loads/saves TOML config files with sensible defaults.

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import tomli_w


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "booklore-enrich"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "booklore": {
        "url": "http://192.168.7.21:6060",
        "username": "",
    },
    "scraping": {
        "rate_limit_seconds": 3,
        "max_concurrent": 1,
        "headless": True,
    },
    "discovery": {
        "romance_tropes": ["enemies-to-lovers", "slow-burn", "forced-proximity"],
        "scifi_tropes": ["space-opera", "first-contact", "cyberpunk"],
        "fantasy_tropes": ["epic-fantasy", "urban-fantasy", "dark-fantasy"],
    },
}


@dataclass
class Config:
    booklore_url: str = "http://192.168.7.21:6060"
    booklore_username: str = ""
    rate_limit_seconds: int = 3
    max_concurrent: int = 1
    headless: bool = True
    romance_tropes: List[str] = field(
        default_factory=lambda: ["enemies-to-lovers", "slow-burn", "forced-proximity"]
    )
    scifi_tropes: List[str] = field(
        default_factory=lambda: ["space-opera", "first-contact", "cyberpunk"]
    )
    fantasy_tropes: List[str] = field(
        default_factory=lambda: ["epic-fantasy", "urban-fantasy", "dark-fantasy"]
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load config from TOML file, falling back to defaults for missing values."""
    if not path.exists():
        return Config()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    booklore = data.get("booklore", {})
    scraping = data.get("scraping", {})
    discovery = data.get("discovery", {})

    return Config(
        booklore_url=booklore.get("url", Config.booklore_url),
        booklore_username=booklore.get("username", Config.booklore_username),
        rate_limit_seconds=scraping.get("rate_limit_seconds", Config.rate_limit_seconds),
        max_concurrent=scraping.get("max_concurrent", Config.max_concurrent),
        headless=scraping.get("headless", Config.headless),
        romance_tropes=discovery.get("romance_tropes", Config().romance_tropes),
        scifi_tropes=discovery.get("scifi_tropes", Config().scifi_tropes),
        fantasy_tropes=discovery.get("fantasy_tropes", Config().fantasy_tropes),
    )


def save_config(config: Config, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save config to TOML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "booklore": {
            "url": config.booklore_url,
            "username": config.booklore_username,
        },
        "scraping": {
            "rate_limit_seconds": config.rate_limit_seconds,
            "max_concurrent": config.max_concurrent,
            "headless": config.headless,
        },
        "discovery": {
            "romance_tropes": config.romance_tropes,
            "scifi_tropes": config.scifi_tropes,
            "fantasy_tropes": config.fantasy_tropes,
        },
    }
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def get_password() -> Optional[str]:
    """Get BookLore password from BOOKLORE_PASSWORD env var or interactive prompt."""
    password = os.environ.get("BOOKLORE_PASSWORD")
    if password:
        return password
    import click
    return click.prompt("BookLore password", hide_input=True)
