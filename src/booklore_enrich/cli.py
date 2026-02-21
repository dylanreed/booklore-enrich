# ABOUTME: Click CLI entry point for booklore-enrich.
# ABOUTME: Defines the main CLI group and registers subcommands.

import click

from booklore_enrich.config import load_config, save_config


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Enrich your BookLore library with metadata from romance.io and thebooknaut.com."""
    pass


@cli.command()
@click.option(
    "--output", "-o", default="booklore-export.csv", help="Output CSV file path."
)
@click.option("--username", "-u", help="BookLore username (overrides config).")
def export(output, username):
    """Export BookLore library as Goodreads-compatible CSV."""
    from booklore_enrich.commands.export import run_export

    if username:
        config = load_config()
        config.booklore_username = username
        save_config(config)
    run_export(output)


@cli.command()
def scrape():
    """Scrape trope/heat metadata from romance.io and thebooknaut.com."""
    click.echo("Scrape not yet implemented.")


@cli.command()
def tag():
    """Push enriched metadata as tags and shelves into BookLore."""
    click.echo("Tag not yet implemented.")


@cli.command()
def discover():
    """Discover new books by trope from romance.io and thebooknaut.com."""
    click.echo("Discover not yet implemented.")
