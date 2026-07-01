"""Celery application — background workers and beat scheduler."""

from __future__ import annotations

from backend.import_roots import ensure_import_paths

ensure_import_paths()

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun, worker_process_init

from backend.config import get_settings


def _build_celery() -> Celery:
    settings = get_settings()
    app = Celery("owlbell")

    app.conf.update(
        broker_url=settings.celery_broker_url,
        result_backend=settings.celery_backend_url,
        task_serializer=settings.celery.task_serializer,
        accept_content=settings.celery.accept_content,
        result_serializer=settings.celery.result_serializer,
        timezone=settings.celery.timezone,
        enable_utc=settings.celery.enable_utc,
        worker_concurrency=settings.celery.worker_concurrency,
        worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
        task_soft_time_limit=settings.celery.task_soft_time_limit,
        task_time_limit=settings.celery.task_time_limit,
        task_acks_late=settings.celery.task_acks_late,
        task_track_started=settings.celery.task_track_started,
        task_default_queue=settings.celery.default_queue,
        imports=(
            "workers.onboarding_tasks",
            "workers.analytics_tasks",
            "workers.reminder_tasks",
            "workers.review_tasks",
            "workers.quote_tasks",
            "workers.missed_call_tasks",
            "workers.report_tasks",
        ),
        task_routes={
            "workers.provision_retell": {"queue": "onboarding"},
            "workers.rollup_yesterday": {"queue": "analytics"},
            "workers.rollup_day": {"queue": "analytics"},
            "workers.send_appointment_reminders": {"queue": "default"},
            "workers.send_review_requests": {"queue": "default"},
            "workers.send_quote_followups": {"queue": "default"},
            "workers.send_missed_call_textbacks": {"queue": "default"},
            "workers.generate_weekly_reports": {"queue": "default"},
        },
        beat_schedule={
            "analytics-daily-rollup": {
                "task": "workers.rollup_yesterday",
                "schedule": crontab(hour=2, minute=0),
                "options": {"queue": "analytics"},
            },
            "appointment-reminders": {
                "task": "workers.send_appointment_reminders",
                "schedule": crontab(minute="*/15"),
                "options": {"queue": "default"},
            },
            "review-requests": {
                "task": "workers.send_review_requests",
                "schedule": crontab(minute=15),
                "options": {"queue": "default"},
            },
            "quote-followups": {
                "task": "workers.send_quote_followups",
                "schedule": crontab(minute=30),
                "options": {"queue": "default"},
            },
            "missed-call-textbacks": {
                "task": "workers.send_missed_call_textbacks",
                "schedule": crontab(minute="*"),
                "options": {"queue": "default"},
            },
            "weekly-ops-reports": {
                "task": "workers.generate_weekly_reports",
                "schedule": crontab(hour=8, minute=0, day_of_week="mon"),
                "options": {"queue": "default"},
            },
        },
    )
    return app


celery_app = _build_celery()


@worker_process_init.connect
def _init_worker_db(**_kwargs) -> None:
    """Initialize DB engine in each forked worker process."""
    from workers.db import ensure_worker_db

    ensure_worker_db()


@task_prerun.connect
def _init_db_before_task(**_kwargs) -> None:
    """Ensure DB is ready before each task (solo pool, eager mode, tests)."""
    from workers.db import ensure_worker_db

    ensure_worker_db()