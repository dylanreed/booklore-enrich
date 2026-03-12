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
@click.option("--from-dir", type=click.Path(exists=True), default=None,
              help="Discover books from filesystem instead of BookLore API")
def scrape(source, limit, from_dir):
    """Scrape trope/heat metadata from romance.io and thebooknaut.com."""
    from booklore_enrich.commands.scrape import run_scrape
    run_scrape(source=source, limit=limit, from_dir=from_dir)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview changes without applying.")
@click.option("--skip-shelves", is_flag=True, help="Skip shelf creation, only add tags.")
@click.option("--skip-tags", is_flag=True, help="Skip tag assignment, only create shelves.")
@click.option("--concurrency", "-c", type=click.IntRange(min=1), default=4, help="Max concurrent API workers.")
def tag(dry_run, skip_shelves, skip_tags, concurrency):
    """Push enriched metadata as tags and shelves into BookLore."""
    from booklore_enrich.commands.tag import run_tag
    run_tag(dry_run, skip_shelves=skip_shelves, skip_tags=skip_tags, concurrency=concurrency)


@cli.command()
@click.option("--source", "-s", type=click.Choice(["romance.io", "booknaut", "all"]),
              default="all", help="Which source to check.")
@click.option("--genre", "-g", type=click.Choice(["romance", "sci-fi", "fantasy"]),
              default=None, help="Filter by genre.")
def discover(source, genre):
    """Discover new books by trope from romance.io and thebooknaut.com."""
    from booklore_enrich.commands.discover import run_discover
    run_discover(source, genre)


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Show what would change without writing")
@click.option("--force", is_flag=True, help="Re-embed already processed books")
def embed(directory, dry_run, force):
    """Write cached metadata into EPUB files."""
    from booklore_enrich.commands.embed import run_embed
    run_embed(directory=directory, dry_run=dry_run, force=force)
