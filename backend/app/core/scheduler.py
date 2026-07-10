import os
import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import settings

scheduler = AsyncIOScheduler()


async def _get_conn():
    return await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        statement_cache_size=0,
    )


async def _get_tenant_schemas():
    conn = await _get_conn()
    try:
        rows = await conn.fetch(
            "SELECT schema_name FROM core.tenants WHERE is_active = TRUE"
        )
        return [r["schema_name"] for r in rows]
    finally:
        await conn.close()


async def _fire_notification(
    conn, schema: str, user_id, event_code: str,
    title: str, body: str, ref_type: str = None, ref_id=None
):
    await conn.execute(
        f"""
        INSERT INTO "{schema}".notifications
            (user_id, event_code, title, body, reference_type, reference_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user_id, event_code, title, body, ref_type, ref_id
    )


# Existing jobs 

async def check_upcoming_reservations():
    if os.getenv("TESTING"):
        return
    schemas = await _get_tenant_schemas()
    for schema in schemas:
        conn = await _get_conn()
        try:
            rows = await conn.fetch(
                f"""
                SELECT hr.id, hr.guest_id, hr.check_in_date
                FROM "{schema}".hotel_reservations hr
                WHERE hr.status = 'confirmed'
                AND hr.check_in_date = CURRENT_DATE
                AND NOT EXISTS (
                    SELECT 1 FROM "{schema}".notifications n
                    WHERE n.event_code = 'reservation.upcoming'
                    AND n.reference_id = hr.id
                    AND n.created_at::date = CURRENT_DATE
                )
                """
            )
            admins = await conn.fetch(
                f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = TRUE'
            )
            for res in rows:
                for admin in admins:
                    await _fire_notification(
                        conn, schema, admin["id"],
                        "reservation.upcoming",
                        "Reservation Today",
                        "A reservation is due today.",
                        "hotel_reservation", res["id"]
                    )
        finally:
            await conn.close()


async def check_cash_register_not_opened():
    if os.getenv("TESTING"):
        return
    schemas = await _get_tenant_schemas()
    for schema in schemas:
        conn = await _get_conn()
        try:
            outlets = await conn.fetch(
                f'SELECT id FROM "{schema}".outlets WHERE is_active = TRUE'
            )
            for outlet in outlets:
                opened = await conn.fetchval(
                    f"""
                    SELECT COUNT(*) FROM "{schema}".cash_register
                    WHERE outlet_id = $1 AND action = 'open'
                    AND created_at::date = CURRENT_DATE
                    """,
                    outlet["id"]
                )
                if not opened:
                    admins = await conn.fetch(
                        f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = TRUE'
                    )
                    for admin in admins:
                        await _fire_notification(
                            conn, schema, admin["id"],
                            "cash.not_opened",
                            "Cash Register Not Opened",
                            "The cash register has not been opened today.",
                            "outlet", outlet["id"]
                        )
        finally:
            await conn.close()


async def check_housekeeping_overdue():
    if os.getenv("TESTING"):
        return
    schemas = await _get_tenant_schemas()
    for schema in schemas:
        conn = await _get_conn()
        try:
            rows = await conn.fetch(
                f"""
                SELECT id, room_id FROM "{schema}".housekeeping_tasks
                WHERE status IN ('pending', 'in_progress')
                AND created_at < NOW() - INTERVAL '4 hours'
                AND NOT EXISTS (
                    SELECT 1 FROM "{schema}".notifications n
                    WHERE n.event_code = 'housekeeping.overdue'
                    AND n.reference_id = housekeeping_tasks.id
                    AND n.created_at > NOW() - INTERVAL '4 hours'
                )
                """
            )
            admins = await conn.fetch(
                f'SELECT id FROM "{schema}".user_profiles WHERE is_admin = TRUE'
            )
            for task in rows:
                for admin in admins:
                    await _fire_notification(
                        conn, schema, admin["id"],
                        "housekeeping.overdue",
                        "Housekeeping Task Overdue",
                        "A housekeeping task is overdue.",
                        "housekeeping_task", task["id"]
                    )
        finally:
            await conn.close()


# Subscription jobs 

async def run_trial_expiry():
    if os.getenv("TESTING"):
        return
    from app.services.subscription_service import job_trial_expiry
    conn = await _get_conn()
    try:
        await job_trial_expiry(conn)
    finally:
        await conn.close()


async def run_grace_and_suspension():
    if os.getenv("TESTING"):
        return
    from app.services.subscription_service import job_grace_and_suspension
    conn = await _get_conn()
    try:
        await job_grace_and_suspension(conn)
    finally:
        await conn.close()


async def run_demo_expiry():
    if os.getenv("TESTING"):
        return
    from app.services.subscription_service import job_demo_expiry
    conn = await _get_conn()
    try:
        await job_demo_expiry(conn)
    finally:
        await conn.close()


# Scheduler start/stop 

def start_scheduler():
    if os.getenv("TESTING"):
        return

    # Existing operational jobs
    scheduler.add_job(check_upcoming_reservations,   "interval", minutes=5)
    scheduler.add_job(check_cash_register_not_opened,"interval", hours=1)
    scheduler.add_job(check_housekeeping_overdue,    "interval", minutes=30)

    # Subscription jobs — run daily at Nepal time
    # Nepal is UTC+5:45, so:
    # 01:00 Nepal = 19:15 UTC previous day
    # 01:30 Nepal = 19:45 UTC previous day
    # 02:00 Nepal = 20:15 UTC previous day
    scheduler.add_job(
        run_trial_expiry,
        trigger="cron",
        hour=19, minute=15,
        id="trial_expiry",
        replace_existing=True
    )
    scheduler.add_job(
        run_grace_and_suspension,
        trigger="cron",
        hour=19, minute=45,
        id="grace_suspension",
        replace_existing=True
    )
    scheduler.add_job(
        run_demo_expiry,
        trigger="cron",
        hour=20, minute=15,
        id="demo_expiry",
        replace_existing=True
    )

    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()