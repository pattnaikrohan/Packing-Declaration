"""
APScheduler setup — Sunday 02:00 weekly retrain using same retrain_if_ready() function.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _scheduled_retrain():
    logger.info("[scheduler] Weekly retrain triggered")
    try:
        from app.training.state import retrain_lock
        from app.training import train_models
        with retrain_lock:
            result = train_models.retrain_if_ready()
        logger.info(f"[scheduler] Weekly retrain complete — swapped={result.swapped}, F1={result.new_f1}")
    except Exception as e:
        logger.error(f"[scheduler] Weekly retrain error: {e}")


def start():
    scheduler.add_job(
        _scheduled_retrain,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_retrain",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[scheduler] APScheduler started — weekly retrain scheduled Sun 02:00")


def stop():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] APScheduler stopped")
