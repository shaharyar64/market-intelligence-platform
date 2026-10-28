import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.instagram import InstagramProfileScrapeRequest
from services.data_scraping_service.app.models.instagram_posts import InstagramPostScrapeRequest
from services.data_scraping_service.app.models.schedules import (
    InstagramScheduleCreate,
    InstagramScheduleUpdate,
    InstagramScheduledPostsPayload,
)
from services.data_scraping_service.app.services.instagram import persist_profiles, scrape_instagram_profiles
from services.data_scraping_service.app.services.instagram_posts import (
    persist_posts,
    scrape_instagram_posts,
    upload_post_images,
)


logger = logging.getLogger(__name__)
_scheduler_task: asyncio.Task | None = None


def _engine():
    from shared.database import Database

    return Database().get_engine()


def scheduler_table_exists() -> bool:
    with _engine().connect() as connection:
        return bool(connection.execute(text(
            "SELECT to_regclass('public.scraping_schedules') IS NOT NULL"
        )).scalar())


def next_run(cron_expression: str, timezone: str, base: datetime | None = None) -> datetime:
    zone = ZoneInfo(timezone)
    base_local = (base or datetime.now(UTC)).astimezone(zone)
    return croniter(cron_expression, base_local).get_next(datetime).astimezone(UTC)


def create_schedule(data: InstagramScheduleCreate) -> dict:
    schedule_id = uuid4()
    next_run_at = next_run(data.cron_expression, data.timezone) if data.enabled else None
    statement = text("""
        INSERT INTO public.scraping_schedules
            (id, name, platform, resource_type, cron_expression, timezone,
             request_payload, enabled, next_run_at)
        VALUES
            (:id, :name, 'instagram', :resource_type, :cron_expression, :timezone,
             CAST(:request_payload AS JSONB), :enabled, :next_run_at)
        RETURNING *
    """)
    import json

    with _engine().begin() as connection:
        row = connection.execute(statement, {
            **data.model_dump(exclude={"request_payload"}),
            "id": schedule_id,
            "request_payload": json.dumps(data.request_payload),
            "next_run_at": next_run_at,
        }).mappings().one()
    return dict(row)


def list_schedules() -> list[dict]:
    with _engine().connect() as connection:
        rows = connection.execute(text(
            "SELECT * FROM public.scraping_schedules WHERE platform = 'instagram' ORDER BY created_at DESC"
        )).mappings().all()
    return [dict(row) for row in rows]


def get_schedule(schedule_id: UUID) -> dict | None:
    with _engine().connect() as connection:
        row = connection.execute(text(
            "SELECT * FROM public.scraping_schedules WHERE id = :id AND platform = 'instagram'"
        ), {"id": schedule_id}).mappings().first()
    return dict(row) if row else None


def update_schedule(schedule_id: UUID, data: InstagramScheduleUpdate) -> dict | None:
    existing = get_schedule(schedule_id)
    if not existing:
        return None
    values = data.model_dump(exclude_none=True)
    if "request_payload" in values:
        import json

        if existing["resource_type"] == "profiles":
            payload = InstagramProfileScrapeRequest.model_validate(values["request_payload"])
            values["request_payload"] = json.dumps(
                payload.model_copy(update={"save_to_database": True}).model_dump(mode="json")
            )
        else:
            payload = InstagramScheduledPostsPayload.model_validate(values["request_payload"])
            values["request_payload"] = json.dumps(payload.model_dump(mode="json"))
    cron = values.get("cron_expression", existing["cron_expression"])
    timezone = values.get("timezone", existing["timezone"])
    enabled = values.get("enabled", existing["enabled"])
    values["next_run_at"] = next_run(cron, timezone) if enabled else None
    values["id"] = schedule_id
    assignments = ", ".join(
        "request_payload = CAST(:request_payload AS JSONB)"
        if key == "request_payload" else f"{key} = :{key}"
        for key in values if key != "id"
    )
    with _engine().begin() as connection:
        row = connection.execute(text(
            f"UPDATE public.scraping_schedules SET {assignments}, updated_at = NOW() WHERE id = :id RETURNING *"
        ), values).mappings().first()
    return dict(row) if row else None


def delete_schedule(schedule_id: UUID) -> bool:
    with _engine().begin() as connection:
        result = connection.execute(text(
            "DELETE FROM public.scraping_schedules WHERE id = :id AND platform = 'instagram'"
        ), {"id": schedule_id})
    return result.rowcount > 0


def claim_due_schedules() -> list[dict]:
    claimed: list[dict] = []
    with _engine().begin() as connection:
        rows = connection.execute(text("""
            SELECT * FROM public.scraping_schedules
            WHERE platform = 'instagram' AND enabled = TRUE AND next_run_at <= NOW()
            ORDER BY next_run_at
            FOR UPDATE SKIP LOCKED
            LIMIT 10
        """)).mappings().all()
        for row in rows:
            item = dict(row)
            upcoming = next_run(item["cron_expression"], item["timezone"])
            connection.execute(text("""
                UPDATE public.scraping_schedules
                SET next_run_at = :next_run, last_started_at = NOW(),
                    last_status = 'running', last_error = NULL, updated_at = NOW()
                WHERE id = :id
            """), {"id": item["id"], "next_run": upcoming})
            claimed.append(item)
    return claimed


def mark_finished(schedule_id, success: bool, error: str | None = None) -> None:
    with _engine().begin() as connection:
        connection.execute(text("""
            UPDATE public.scraping_schedules
            SET last_finished_at = NOW(),
                last_success_at = CASE WHEN :success THEN NOW() ELSE last_success_at END,
                last_status = CASE WHEN :success THEN 'completed' ELSE 'failed' END,
                last_error = :error, updated_at = NOW()
            WHERE id = :id
        """), {"id": schedule_id, "success": success, "error": error})


def mark_started(schedule_id) -> None:
    with _engine().begin() as connection:
        connection.execute(text("""
            UPDATE public.scraping_schedules
            SET last_started_at = NOW(), last_status = 'running',
                last_error = NULL, updated_at = NOW()
            WHERE id = :id
        """), {"id": schedule_id})


async def execute_schedule(schedule: dict) -> None:
    try:
        payload = schedule["request_payload"]
        if schedule["resource_type"] == "profiles":
            request = InstagramProfileScrapeRequest.model_validate(payload).model_copy(
                update={"save_to_database": True}
            )
            profiles = await scrape_instagram_profiles(request)
            await persist_profiles(profiles)
        else:
            config = InstagramScheduledPostsPayload.model_validate(payload)
            zone = ZoneInfo(schedule["timezone"])
            end_date = datetime.now(zone).date()
            if schedule.get("last_success_at"):
                start_date = schedule["last_success_at"].astimezone(zone).date()
                start_date = max(start_date, config.initial_start_date)
            else:
                start_date = config.initial_start_date
            request = InstagramPostScrapeRequest(
                usernames=config.usernames,
                start_date=start_date,
                end_date=end_date,
                max_items_per_username=config.max_items_per_username,
                upload_images_to_s3=config.upload_images_to_s3,
                save_to_database=True,
            )
            posts = await scrape_instagram_posts(request)
            if request.upload_images_to_s3:
                await upload_post_images(posts)
            await persist_posts(posts)
        await asyncio.to_thread(mark_finished, schedule["id"], True)
    except Exception as exc:
        logger.exception("Scheduled Instagram scrape failed: %s", schedule["id"])
        await asyncio.to_thread(mark_finished, schedule["id"], False, str(exc)[:2000])


async def scheduler_loop() -> None:
    while True:
        try:
            schedules = await asyncio.to_thread(claim_due_schedules)
            for schedule in schedules:
                asyncio.create_task(execute_schedule(schedule))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler polling failed")
        await asyncio.sleep(get_settings().SCHEDULER_POLL_SECONDS)


def start_scheduler() -> asyncio.Task:
    global _scheduler_task
    _scheduler_task = asyncio.create_task(scheduler_loop())
    return _scheduler_task


async def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
