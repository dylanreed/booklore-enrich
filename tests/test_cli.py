# ABOUTME: Tests for the CLI entry point and command registration.
# ABOUTME: Verifies all commands are registered and --help works.

from click.testing import CliRunner
from booklore_enrich.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Enrich your BookLore library" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_export_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "--help"])
    assert result.exit_code == 0
    assert "Export BookLore library" in result.output


def test_scrape_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["scrape", "--help"])
    assert result.exit_code == 0


def test_tag_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["tag", "--help"])
    assert result.exit_code == 0


def test_discover_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["discover", "--help"])
    assert result.exit_code == 0


def test_tag_command_has_skip_shelves_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["tag", "--help"])
    assert "--skip-shelves" in result.output


def test_tag_command_has_skip_tags_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["tag", "--help"])
    assert "--skip-tags" in result.output
