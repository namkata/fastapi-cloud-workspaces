"""
Cron-based storage cleanup scheduler.

This module provides cron job functionality for automated storage cleanup
in environments where Celery is not available.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import click
from structlog import get_logger

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.modules.storage.cleanup import run_cleanup_job

logger = get_logger(__name__)


@click.group()
def cli():
    """Storage cleanup cron jobs."""
    pass


@cli.command()
@click.option('--dry-run', is_flag=True, help='Only report what would be cleaned up')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cleanup_orphaned_files(dry_run: bool = False, verbose: bool = False):
    """Clean up orphaned files on disk."""
    if verbose:
        click.echo(f"Starting orphaned files cleanup (dry_run={dry_run})")

    try:
        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=True,
            cleanup_orphaned_records=False,
            cleanup_soft_deleted=False
        ))

        orphaned_results = results["orphaned_files"]
        files_deleted = orphaned_results.get("files_deleted", 0)
        bytes_freed = orphaned_results.get("bytes_freed", 0)

        if dry_run:
            click.echo(f"Would delete {files_deleted} orphaned files ({bytes_freed} bytes)")
        else:
            click.echo(f"Deleted {files_deleted} orphaned files ({bytes_freed} bytes freed)")

        if verbose:
            click.echo(f"Full results: {results}")

    except Exception as e:
        click.echo(f"Error during orphaned files cleanup: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Only report what would be cleaned up')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cleanup_orphaned_records(dry_run: bool = False, verbose: bool = False):
    """Clean up orphaned database records."""
    if verbose:
        click.echo(f"Starting orphaned records cleanup (dry_run={dry_run})")

    try:
        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=False,
            cleanup_orphaned_records=True,
            cleanup_soft_deleted=False
        ))

        orphaned_results = results["orphaned_records"]
        records_deleted = orphaned_results.get("records_deleted", 0)

        if dry_run:
            click.echo(f"Would delete {records_deleted} orphaned records")
        else:
            click.echo(f"Deleted {records_deleted} orphaned records")

        if verbose:
            click.echo(f"Full results: {results}")

    except Exception as e:
        click.echo(f"Error during orphaned records cleanup: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Only report what would be cleaned up')
@click.option('--older-than-days', default=30, help='Delete files older than N days')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cleanup_soft_deleted(dry_run: bool = False, older_than_days: int = 30, verbose: bool = False):
    """Clean up soft-deleted files."""
    if verbose:
        click.echo(f"Starting soft-deleted cleanup (dry_run={dry_run}, older_than_days={older_than_days})")

    try:
        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=False,
            cleanup_orphaned_records=False,
            cleanup_soft_deleted=True,
            soft_deleted_days=older_than_days
        ))

        soft_deleted_results = results["soft_deleted"]
        files_deleted = soft_deleted_results.get("files_deleted", 0)
        records_deleted = soft_deleted_results.get("records_deleted", 0)
        bytes_freed = soft_deleted_results.get("bytes_freed", 0)

        if dry_run:
            click.echo(f"Would delete {files_deleted} files and {records_deleted} records ({bytes_freed} bytes)")
        else:
            click.echo(f"Deleted {files_deleted} files and {records_deleted} records ({bytes_freed} bytes freed)")

        if verbose:
            click.echo(f"Full results: {results}")

    except Exception as e:
        click.echo(f"Error during soft-deleted cleanup: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Only report what would be cleaned up')
@click.option('--soft-deleted-days', default=30, help='Delete soft-deleted files older than N days')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def full_cleanup(dry_run: bool = False, soft_deleted_days: int = 30, verbose: bool = False):
    """Run complete storage cleanup."""
    if verbose:
        click.echo(f"Starting full cleanup (dry_run={dry_run}, soft_deleted_days={soft_deleted_days})")

    try:
        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=True,
            cleanup_orphaned_records=True,
            cleanup_soft_deleted=True,
            soft_deleted_days=soft_deleted_days
        ))

        # Calculate totals
        total_files_deleted = (
            results["orphaned_files"].get("files_deleted", 0) +
            results["soft_deleted"].get("files_deleted", 0)
        )
        total_records_deleted = (
            results["orphaned_records"].get("records_deleted", 0) +
            results["soft_deleted"].get("records_deleted", 0)
        )
        total_bytes_freed = (
            results["orphaned_files"].get("bytes_freed", 0) +
            results["soft_deleted"].get("bytes_freed", 0)
        )

        if dry_run:
            click.echo(f"Would delete {total_files_deleted} files and {total_records_deleted} records ({total_bytes_freed} bytes)")
        else:
            click.echo(f"Deleted {total_files_deleted} files and {total_records_deleted} records ({total_bytes_freed} bytes freed)")

        if verbose:
            click.echo("Detailed results:")
            click.echo(f"  Orphaned files: {results['orphaned_files']}")
            click.echo(f"  Orphaned records: {results['orphaned_records']}")
            click.echo(f"  Soft-deleted: {results['soft_deleted']}")

    except Exception as e:
        click.echo(f"Error during full cleanup: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def storage_stats(verbose: bool = False):
    """Get storage statistics."""
    if verbose:
        click.echo("Getting storage statistics...")

    try:
        from app.core.database import get_db_session
        from app.modules.storage.cleanup import StorageCleanupService

        async def get_stats():
            async with get_db_session() as db:
                cleanup_service = StorageCleanupService(db)
                return await cleanup_service.get_storage_stats()

        stats = asyncio.run(get_stats())

        click.echo("Storage Statistics:")
        click.echo(f"  Total files: {stats['total_files']}")
        click.echo(f"  Total size: {stats['total_size']} bytes")
        click.echo(f"  Active files: {stats['active_files']}")
        click.echo(f"  Active size: {stats['active_size']} bytes")
        click.echo(f"  Soft-deleted files: {stats['soft_deleted_files']}")
        click.echo(f"  Soft-deleted size: {stats['soft_deleted_size']} bytes")

        if verbose:
            click.echo(f"Full stats: {stats}")

    except Exception as e:
        click.echo(f"Error getting storage statistics: {e}", err=True)
        sys.exit(1)


def create_crontab_entries() -> str:
    """
    Generate crontab entries for storage cleanup jobs.

    Returns:
        String with crontab entries
    """
    script_path = Path(__file__).absolute()
    python_path = sys.executable

    entries = [
        "# Storage cleanup cron jobs",
        "# Clean up orphaned files daily at 2:00 AM",
        f"0 2 * * * {python_path} {script_path} cleanup-orphaned-files",
        "",
        "# Clean up orphaned records daily at 2:30 AM",
        f"30 2 * * * {python_path} {script_path} cleanup-orphaned-records",
        "",
        "# Clean up soft-deleted files weekly on Sunday at 3:00 AM",
        f"0 3 * * 0 {python_path} {script_path} cleanup-soft-deleted --older-than-days 30",
        "",
        "# Get storage stats every hour",
        f"0 * * * * {python_path} {script_path} storage-stats",
        "",
    ]

    return "\n".join(entries)


@cli.command()
def generate_crontab():
    """Generate crontab entries for storage cleanup jobs."""
    entries = create_crontab_entries()
    click.echo("Add these entries to your crontab (crontab -e):")
    click.echo()
    click.echo(entries)
    click.echo()
    click.echo("To install automatically, run:")
    click.echo("python cron.py generate-crontab | crontab -")


if __name__ == "__main__":
    cli()
