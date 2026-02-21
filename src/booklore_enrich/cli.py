# ABOUTME: Click CLI entry point for booklore-enrich.
# ABOUTME: Defines the main CLI group and registers subcommands.

import click
from dotenv import load_dotenv

from booklore_enrich.config import load_config, save_config

load_dotenv()


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
@click.option("--source", "-s", type=click.Choice(["romance.io", "booknaut", "all"]),
              default="all", help="Which source to scrape.")
@click.option("--limit", "-l", type=int, default=0, help="Max books to scrape per source (0=all).")
def scrape(source, limit):
    """Scrape trope/heat metadata from romance.io and thebooknaut.com."""
    from booklore_enrich.commands.scrape import run_scrape
    run_scrape(source, limit)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview changes without applying.")
def tag(dry_run):
    """Push enriched metadata as tags and shelves into BookLore."""
    from booklore_enrich.commands.tag import run_tag
    run_tag(dry_run)


@cli.command()
@click.option("--source", "-s", type=click.Choice(["romance.io", "booknaut", "all"]),
              default="all", help="Which source to check.")
@click.option("--genre", "-g", type=click.Choice(["romance", "sci-fi", "fantasy"]),
              default=None, help="Filter by genre.")
def discover(source, genre):
    """Discover new books by trope from romance.io and thebooknaut.com."""
    from booklore_enrich.commands.discover import run_discover
    run_discover(source, genre)
