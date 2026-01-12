"""
Scheduled cleanup job for removing old failed uploads.
"""

from apscheduler.schedulers.background import BackgroundScheduler

from app.utils.file_cleanup import cleanup_orphaned_files


def start_cleanup_scheduler():
    """Start the background scheduler for cleanup jobs."""
    scheduler = BackgroundScheduler()

    # Run cleanup daily at 2 AM
    scheduler.add_job(
        cleanup_orphaned_files,
        "cron",
        hour=2,
        minute=0,
        id="daily_cleanup",
        name="Clean up failed uploads",
        replace_existing=True,
    )

    scheduler.start()
    print("[Scheduler] Started cleanup scheduler (runs daily at 2 AM)")

    return scheduler


# Global scheduler instance
cleanup_scheduler = None


def get_cleanup_scheduler():
    """Get or create the cleanup scheduler."""
    global cleanup_scheduler
    if cleanup_scheduler is None:
        cleanup_scheduler = start_cleanup_scheduler()
    return cleanup_scheduler
