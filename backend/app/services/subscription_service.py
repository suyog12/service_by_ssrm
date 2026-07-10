from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from app.utils.email import send_subscription_email


# Helpers 

APP_URL = "https://suyog12.github.io/suyog-mainali-portfolio/"
ADMIN_EMAIL = "mainalisuyog0@gmail.com"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_tenant(db, schema: str) -> dict:
    row = await db.fetchrow(
        """
        SELECT
            t.id, t.name, t.email,
            t.subscription_status, t.subscription_tier,
            t.trial_days, t.trial_ends_at,
            t.is_demo, t.demo_ends_at, t.demo_plan,
            t.current_period_start, t.current_period_end,
            t.grace_period_days, t.grace_period_ends_at,
            t.suspended_at, t.cancelled_at,
            t.max_outlets, t.max_staff, t.max_menu_items
        FROM core.tenants t
        WHERE t.schema_name = $1
        """,
        schema
    )
    if not row:
        raise HTTPException(404, "Tenant not found")
    return dict(row)


async def _get_plan(db, plan_code: str) -> dict:
    row = await db.fetchrow(
        "SELECT * FROM core.subscription_plans WHERE plan_code = $1",
        plan_code
    )
    return dict(row) if row else None


async def _insert_event(
    db,
    tenant_id: UUID,
    event_type: str,
    from_status: str = None,
    to_status: str = None,
    from_tier: str = None,
    to_tier: str = None,
    period_start: datetime = None,
    period_end: datetime = None,
    amount_npr: float = None,
    payment_reference: str = None,
    notes: str = None,
    created_by: str = "system"
):
    await db.execute(
        """
        INSERT INTO core.subscription_events
            (tenant_id, event_type, from_status, to_status, from_tier, to_tier,
             period_start, period_end, amount_npr, payment_reference, notes, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """,
        tenant_id, event_type, from_status, to_status, from_tier, to_tier,
        period_start, period_end, amount_npr, payment_reference, notes, created_by
    )


def _info_box(rows: list) -> str:
    """Inline info box for subscription emails."""
    cells = ""
    for label, value in rows:
        cells += f"""
        <tr>
          <td style="padding:8px 16px; color:#6B7280; font-size:13px;
                     font-weight:600; white-space:nowrap; width:1%;">{label}</td>
          <td style="padding:8px 16px; color:#111827; font-size:14px;">{value}</td>
        </tr>"""
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#F9FAFB; border:1px solid #E5E7EB;
                  border-radius:8px; margin:20px 0;">
      {cells}
    </table>"""


async def _send(
    to_email: str,
    subject: str,
    heading: str,
    body_html: str,
    cta_text: str = None,
    cta_url: str = None,
    footer_note: str = None,
) -> None:
    try:
        await send_subscription_email(
            to=to_email,
            subject=subject,
            heading=heading,
            body_html=body_html,
            cta_text=cta_text,
            cta_url=cta_url,
            footer_note=footer_note,
        )
    except Exception:
        pass


# Subscription state check (called on every request) 

async def check_subscription_access(schema: str, db) -> None:
    row = await db.fetchrow(
        """
        SELECT subscription_status, trial_ends_at, demo_ends_at,
               grace_period_ends_at, is_demo
        FROM core.tenants
        WHERE schema_name = $1
        """,
        schema
    )
    if not row:
        return

    status = row["subscription_status"]
    now = _now()

    if status == "trialing":
        if row["trial_ends_at"] and row["trial_ends_at"] < now:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "trial_expired",
                    "message": "Your free trial has expired. Please subscribe to continue using Service by SSRM.",
                    "action": "renew"
                }
            )

    elif status == "demo":
        if row["demo_ends_at"] and row["demo_ends_at"] < now:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "demo_expired",
                    "message": "Your demo period has ended. Please contact us to subscribe.",
                    "action": "contact"
                }
            )

    elif status == "past_due":
        if row["grace_period_ends_at"] and row["grace_period_ends_at"] < now:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "grace_expired",
                    "message": "Your grace period has expired. Please renew your subscription to restore access.",
                    "action": "renew"
                }
            )

    elif status == "suspended":
        raise HTTPException(
            status_code=402,
            detail={
                "code": "suspended",
                "message": "Your account has been suspended. Please renew your subscription or contact support.",
                "action": "renew"
            }
        )

    elif status == "cancelled":
        raise HTTPException(
            status_code=402,
            detail={
                "code": "cancelled",
                "message": "Your account has been cancelled. Please contact support to reactivate.",
                "action": "contact"
            }
        )


# Plan features 

async def get_plan_restrictions(db, plan_code: str) -> set:
    rows = await db.fetch(
        """
        SELECT feature_code
        FROM core.plan_features
        WHERE plan_code = $1 AND is_included = FALSE
        """,
        plan_code
    )
    return {r["feature_code"] for r in rows}


# Usage limit enforcement 

async def check_outlet_limit(db, schema: str) -> None:
    tenant = await db.fetchrow(
        "SELECT max_outlets FROM core.tenants WHERE schema_name = $1", schema
    )
    if not tenant or tenant["max_outlets"] is None:
        return
    count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".outlets WHERE is_active = TRUE'
    )
    if count >= tenant["max_outlets"]:
        raise HTTPException(
            status_code=403,
            detail=f"You have reached the outlet limit ({tenant['max_outlets']}) for your plan. Please upgrade to add more outlets."
        )


async def check_staff_limit(db, schema: str) -> None:
    tenant = await db.fetchrow(
        "SELECT max_staff FROM core.tenants WHERE schema_name = $1", schema
    )
    if not tenant or tenant["max_staff"] is None:
        return
    count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".user_profiles WHERE is_admin = FALSE'
    )
    if count >= tenant["max_staff"]:
        raise HTTPException(
            status_code=403,
            detail=f"You have reached the staff limit ({tenant['max_staff']}) for your plan. Please upgrade to add more staff."
        )


async def check_menu_item_limit(db, schema: str, outlet_id: UUID) -> None:
    tenant = await db.fetchrow(
        "SELECT max_menu_items FROM core.tenants WHERE schema_name = $1", schema
    )
    if not tenant or tenant["max_menu_items"] is None:
        return
    count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".menu_items WHERE outlet_id = $1',
        outlet_id
    )
    if count >= tenant["max_menu_items"]:
        raise HTTPException(
            status_code=403,
            detail=f"You have reached the menu item limit ({tenant['max_menu_items']}) for your plan. Please upgrade to add more items."
        )


# Registration — set trial on new tenant 

async def initialize_trial(db, tenant_id: UUID, schema: str) -> None:
    pro_plan = await _get_plan(db, "pro")
    trial_days = 14

    trial_ends_at = _now() + timedelta(days=trial_days)
    current_period_start = _now()

    max_outlets    = pro_plan["max_outlets"]    if pro_plan else 3
    max_staff      = pro_plan["max_staff"]      if pro_plan else 30
    max_menu_items = pro_plan["max_menu_items"] if pro_plan else 500

    await db.execute(
        """
        UPDATE core.tenants SET
            subscription_status  = 'trialing',
            subscription_tier    = 'pro',
            trial_days           = $1,
            trial_ends_at        = $2,
            current_period_start = $3,
            max_outlets          = $4,
            max_staff            = $5,
            max_menu_items       = $6,
            updated_at           = NOW()
        WHERE id = $7
        """,
        trial_days, trial_ends_at, current_period_start,
        max_outlets, max_staff, max_menu_items,
        tenant_id
    )

    await _insert_event(
        db,
        tenant_id=tenant_id,
        event_type="trial_started",
        from_status=None,
        to_status="trialing",
        to_tier="pro",
        period_start=current_period_start,
        period_end=trial_ends_at,
        notes=f"Trial started for {trial_days} days on pro plan"
    )


# Tenant-facing read endpoints 

async def get_subscription(db, schema: str) -> dict:
    tenant = await _get_tenant(db, schema)
    plan = await _get_plan(db, tenant["subscription_tier"])

    now = _now()
    trial_days_remaining = None
    grace_days_remaining = None

    if tenant["subscription_status"] == "trialing" and tenant["trial_ends_at"]:
        delta = tenant["trial_ends_at"] - now
        trial_days_remaining = max(0, delta.days)

    if tenant["subscription_status"] == "past_due" and tenant["grace_period_ends_at"]:
        delta = tenant["grace_period_ends_at"] - now
        grace_days_remaining = max(0, delta.days)

    outlet_count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".outlets WHERE is_active = TRUE'
    )
    staff_count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".user_profiles WHERE is_admin = FALSE'
    )
    menu_item_count = await db.fetchval(
        f'SELECT COUNT(*) FROM "{schema}".menu_items'
    )

    return {
        "status": tenant["subscription_status"],
        "tier": tenant["subscription_tier"],
        "plan": {
            "plan_code":         plan["plan_code"]         if plan else tenant["subscription_tier"],
            "display_name":      plan["display_name"]      if plan else tenant["subscription_tier"].title(),
            "price_monthly_npr": plan["price_monthly_npr"] if plan else None,
            "price_annual_npr":  plan["price_annual_npr"]  if plan else None,
            "max_outlets":       plan["max_outlets"]       if plan else None,
            "max_staff":         plan["max_staff"]         if plan else None,
            "max_menu_items":    plan["max_menu_items"]    if plan else None,
        } if plan else None,
        "is_demo":                     tenant["is_demo"],
        "trial_ends_at":               tenant["trial_ends_at"],
        "trial_days_remaining":        trial_days_remaining,
        "demo_ends_at":                tenant["demo_ends_at"],
        "current_period_start":        tenant["current_period_start"],
        "current_period_end":          tenant["current_period_end"],
        "grace_period_ends_at":        tenant["grace_period_ends_at"],
        "grace_period_days_remaining": grace_days_remaining,
        "cancelled_at":                tenant["cancelled_at"],
        "suspended_at":                tenant["suspended_at"],
        "usage": {
            "outlets":    {"used": outlet_count,    "limit": tenant["max_outlets"]},
            "staff":      {"used": staff_count,     "limit": tenant["max_staff"]},
            "menu_items": {"used": menu_item_count, "limit": tenant["max_menu_items"]},
        }
    }


async def get_plans(db) -> list:
    rows = await db.fetch(
        "SELECT * FROM core.subscription_plans WHERE is_active = TRUE ORDER BY price_monthly_npr NULLS LAST"
    )
    return [dict(r) for r in rows]


async def get_history(db, schema: str) -> list:
    tenant = await db.fetchrow(
        "SELECT id FROM core.tenants WHERE schema_name = $1", schema
    )
    if not tenant:
        return []
    rows = await db.fetch(
        """
        SELECT * FROM core.subscription_events
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        """,
        tenant["id"]
    )
    return [dict(r) for r in rows]


async def get_renew_info(db, schema: str) -> dict:
    tenant = await _get_tenant(db, schema)
    plan = await _get_plan(db, tenant["subscription_tier"])

    return {
        "plan_code":         tenant["subscription_tier"],
        "plan_display_name": plan["display_name"] if plan else tenant["subscription_tier"].title(),
        "price_monthly_npr": plan["price_monthly_npr"] if plan else None,
        "qr_image_url":      "https://pub-placeholder.r2.dev/ssrm-payment-qr.png",
        "payment_instructions": (
            "1. Scan the QR code using your eSewa, Khalti, or FonePay app.\n"
            "2. Send the exact amount shown for your plan.\n"
            "3. Take a screenshot of the payment confirmation.\n"
            "4. Upload the screenshot and enter your transaction reference below.\n"
            "5. Your account will be activated within a few hours once verified."
        ),
        "reference_format": "Use your business name and phone number as the payment reference. Example: HotelSunrise-9841234567"
    }


async def submit_payment_receipt(
    db,
    schema: str,
    data: dict,
    tenant_admin_email: str
) -> dict:
    tenant = await db.fetchrow(
        "SELECT id, name FROM core.tenants WHERE schema_name = $1", schema
    )
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    existing = await db.fetchrow(
        """
        SELECT id FROM core.payment_receipts
        WHERE tenant_id = $1 AND status = 'pending_verification'
        """,
        tenant["id"]
    )
    if existing:
        raise HTTPException(
            400,
            "You already have a payment receipt pending verification. Please wait for it to be reviewed."
        )

    row = await db.fetchrow(
        """
        INSERT INTO core.payment_receipts
            (tenant_id, plan_code, amount_npr, payment_reference, receipt_url, receipt_key)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        tenant["id"],
        data["plan_code"],
        data["amount_npr"],
        data["payment_reference"],
        data["receipt_url"],
        data["receipt_key"]
    )

    # Notify super admin
    await _send(
        to_email=ADMIN_EMAIL,
        subject=f"New payment receipt from {tenant['name']}",
        heading="New Payment Receipt Submitted",
        body_html=f"""
        <p>A tenant has submitted a payment receipt and is awaiting verification.</p>
        {_info_box([
            ("Tenant", tenant['name']),
            ("Plan", data['plan_code'].upper()),
            ("Amount", f"NPR {data['amount_npr']:,.2f}"),
            ("Reference", data['payment_reference']),
            ("Schema", schema),
        ])}
        <p>
            The receipt image is available below. Log in to the Admin Portal
            to review and confirm this payment.
        </p>
        <p>
            <a href="{data['receipt_url']}"
               style="color:#4F46E5; text-decoration:none; font-weight:600;">
                View Receipt Image &rarr;
            </a>
        </p>""",
        cta_text="Open Admin Portal",
        cta_url=f"https://suyog12.github.io/suyog-mainali-portfolio/",
        footer_note="This is an automated notification. Do not reply to this email."
    )

    return dict(row)


# APScheduler jobs 

async def job_trial_expiry(db) -> None:
    """
    Runs daily at 01:00 Nepal time.
    - Tenants whose trial has expired -> past_due
    - Tenants with trial ending in 3 days -> warning email
    - Tenants with trial ending tomorrow -> urgent email
    """
    now = _now()
    tomorrow = now + timedelta(days=1)
    in_3_days = now + timedelta(days=3)

    # Expire trials
    expired = await db.fetch(
        """
        SELECT id, name, email, subscription_tier, trial_ends_at, grace_period_days
        FROM core.tenants
        WHERE subscription_status = 'trialing'
          AND trial_ends_at < $1
        """,
        now
    )
    for t in expired:
        grace_ends = t["trial_ends_at"] + timedelta(days=t["grace_period_days"])
        await db.execute(
            """
            UPDATE core.tenants SET
                subscription_status  = 'past_due',
                grace_period_ends_at = $1,
                updated_at           = NOW()
            WHERE id = $2
            """,
            grace_ends, t["id"]
        )
        await _insert_event(
            db,
            tenant_id=t["id"],
            event_type="trial_expired",
            from_status="trialing",
            to_status="past_due",
            notes=f"Trial expired. Grace period ends {grace_ends.date()}"
        )
        await _send(
            to_email=t["email"],
            subject="Your free trial has ended — renew to keep access",
            heading="Your Free Trial Has Ended",
            body_html=f"""
            <p>Dear {t['name']},</p>
            <p>
                Your 14-day free trial on <strong>Service by SSRM</strong> has ended.
                Your account is currently in a grace period and will be suspended if
                payment is not received by the deadline below.
            </p>
            {_info_box([
                ("Account", t['name']),
                ("Trial ended", str(t['trial_ends_at'].date())),
                ("Grace period ends", str(grace_ends.date())),
                ("Days remaining", str(t['grace_period_days'])),
            ])}
            <p>
                Log in to your dashboard and go to
                <strong>Settings &rarr; Subscription</strong> to submit a payment
                and keep your account active.
            </p>""",
            cta_text="Renew My Subscription",
            cta_url=f"{APP_URL}/settings/subscription",
            footer_note="Your data is safe. We will retain it for 30 days after suspension."
        )

    # 3-day warning
    warning_3 = await db.fetch(
        """
        SELECT id, name, email, trial_ends_at
        FROM core.tenants
        WHERE subscription_status = 'trialing'
          AND trial_ends_at::date = $1::date
        """,
        in_3_days
    )
    for t in warning_3:
        await _send(
            to_email=t["email"],
            subject="Your free trial expires in 3 days",
            heading="Your Trial Expires in 3 Days",
            body_html=f"""
            <p>Dear {t['name']},</p>
            <p>
                Your free trial on <strong>Service by SSRM</strong> expires on
                <strong>{t['trial_ends_at'].date()}</strong>.
                Subscribe now to avoid any interruption to your operations.
            </p>
            {_info_box([
                ("Account", t['name']),
                ("Trial ends", str(t['trial_ends_at'].date())),
                ("Days remaining", "3"),
            ])}
            <p>
                Go to <strong>Settings &rarr; Subscription</strong> in your dashboard
                to choose a plan and submit your payment.
            </p>""",
            cta_text="Subscribe Now",
            cta_url=f"{APP_URL}/settings/subscription",
            footer_note="No action is needed if you have already submitted a payment receipt."
        )

    # Tomorrow warning
    warning_1 = await db.fetch(
        """
        SELECT id, name, email, trial_ends_at
        FROM core.tenants
        WHERE subscription_status = 'trialing'
          AND trial_ends_at::date = $1::date
        """,
        tomorrow
    )
    for t in warning_1:
        await _send(
            to_email=t["email"],
            subject="Your free trial expires tomorrow — act now",
            heading="Your Trial Expires Tomorrow",
            body_html=f"""
            <p>Dear {t['name']},</p>
            <p>
                This is an urgent reminder that your free trial on
                <strong>Service by SSRM</strong> expires <strong>tomorrow,
                {t['trial_ends_at'].date()}</strong>.
            </p>
            {_info_box([
                ("Account", t['name']),
                ("Trial ends", str(t['trial_ends_at'].date())),
                ("Time remaining", "Less than 24 hours"),
            ])}
            <p>
                Subscribe today to keep your account and data active without
                any interruption.
            </p>""",
            cta_text="Subscribe Today",
            cta_url=f"{APP_URL}/settings/subscription",
            footer_note="If you have already submitted a payment receipt, you can ignore this email."
        )


async def job_grace_and_suspension(db) -> None:
    """
    Runs daily at 01:30 Nepal time.
    - Tenants whose grace period has expired -> suspended
    - Tenants with grace ending tomorrow -> final warning email
    """
    now = _now()
    tomorrow = now + timedelta(days=1)

    # Suspend
    to_suspend = await db.fetch(
        """
        SELECT id, name, email
        FROM core.tenants
        WHERE subscription_status = 'past_due'
          AND grace_period_ends_at < $1
        """,
        now
    )
    for t in to_suspend:
        await db.execute(
            """
            UPDATE core.tenants SET
                subscription_status = 'suspended',
                suspended_at        = NOW(),
                updated_at          = NOW()
            WHERE id = $1
            """,
            t["id"]
        )
        await _insert_event(
            db,
            tenant_id=t["id"],
            event_type="suspended",
            from_status="past_due",
            to_status="suspended",
            notes="Grace period expired — account suspended"
        )
        await _send(
            to_email=t["email"],
            subject="Your Service by SSRM account has been suspended",
            heading="Account Suspended",
            body_html=f"""
            <p>Dear {t['name']},</p>
            <p>
                Your account on <strong>Service by SSRM</strong> has been suspended
                due to non-payment. Your data is safe and will be retained for
                <strong>30 days</strong>.
            </p>
            {_info_box([
                ("Account", t['name']),
                ("Status", "Suspended"),
                ("Data retained until", "30 days from suspension"),
            ])}
            <p>
                To restore access, log in to your dashboard and go to
                <strong>Settings &rarr; Subscription</strong> to submit a payment receipt.
                Your account will be reactivated within a few hours of payment confirmation.
            </p>""",
            cta_text="Restore My Account",
            cta_url=f"{APP_URL}/settings/subscription",
            footer_note="If you believe this is an error, please contact support."
        )

    # Final warning
    final_warning = await db.fetch(
        """
        SELECT id, name, email, grace_period_ends_at
        FROM core.tenants
        WHERE subscription_status = 'past_due'
          AND grace_period_ends_at::date = $1::date
        """,
        tomorrow
    )
    for t in final_warning:
        await _send(
            to_email=t["email"],
            subject="Final notice — your account will be suspended tomorrow",
            heading="Final Notice: Suspension Tomorrow",
            body_html=f"""
            <p>Dear {t['name']},</p>
            <p>
                This is your final notice. Your <strong>Service by SSRM</strong> account
                will be <strong>suspended tomorrow, {t['grace_period_ends_at'].date()}</strong>,
                if payment is not received.
            </p>
            {_info_box([
                ("Account", t['name']),
                ("Suspension date", str(t['grace_period_ends_at'].date())),
                ("Time remaining", "Less than 24 hours"),
            ])}
            <p>
                Submit your payment receipt now from
                <strong>Settings &rarr; Subscription</strong> to avoid suspension.
            </p>""",
            cta_text="Submit Payment Now",
            cta_url=f"{APP_URL}/settings/subscription",
            footer_note="Your data will be retained for 30 days after suspension."
        )


async def job_demo_expiry(db) -> None:
    """
    Runs daily at 02:00 Nepal time.
    - Tenants whose demo has expired -> suspended
    - Tenants with demo ending tomorrow -> warning email
    """
    now = _now()
    tomorrow = now + timedelta(days=1)

    # Expire demos
    expired = await db.fetch(
        """
        SELECT id, name, email
        FROM core.tenants
        WHERE subscription_status = 'demo'
          AND demo_ends_at < $1
        """,
        now
    )
    for t in expired:
        await db.execute(
            """
            UPDATE core.tenants SET
                subscription_status = 'suspended',
                suspended_at        = NOW(),
                updated_at          = NOW()
            WHERE id = $1
            """,
            t["id"]
        )
        await _insert_event(
            db,
            tenant_id=t["id"],
            event_type="demo_expired",
            from_status="demo",
            to_status="suspended",
            notes="Demo period ended — account suspended"
        )
        await _send(
            to_email=t["email"],
            subject="Your Service by SSRM demo has ended",
            heading="Your Demo Period Has Ended",
            body_html=f"""
            <p>Dear {t['name']},</p>
            <p>
                Your demo period on <strong>Service by SSRM</strong> has ended and
                your account has been suspended.
            </p>
            {_info_box([
                ("Account", t['name']),
                ("Status", "Demo ended — suspended"),
            ])}
            <p>
                To continue using Service by SSRM, please contact us to set up
                a subscription. We will reactivate your account within one business day.
            </p>""",
            cta_text="Contact Us",
            cta_url=f"https://suyog12.github.io/suyog-mainali-portfolio/",
            footer_note="Your data is safe and will be retained for 30 days."
        )

    # Tomorrow warning
    warning = await db.fetch(
        """
        SELECT id, name, email, demo_ends_at
        FROM core.tenants
        WHERE subscription_status = 'demo'
          AND demo_ends_at::date = $1::date
        """,
        tomorrow
    )
    for t in warning:
        await _send(
            to_email=t["email"],
            subject="Your Service by SSRM demo expires tomorrow",
            heading="Your Demo Expires Tomorrow",
            body_html=f"""
            <p>Dear {t['name']},</p>
            <p>
                Your demo period on <strong>Service by SSRM</strong> expires tomorrow,
                <strong>{t['demo_ends_at'].date()}</strong>.
            </p>
            {_info_box([
                ("Account", t['name']),
                ("Demo ends", str(t['demo_ends_at'].date())),
            ])}
            <p>
                Please contact us today to set up a subscription and continue using
                Service by SSRM without interruption.
            </p>""",
            cta_text="Contact Us",
            cta_url=f"https://suyog12.github.io/suyog-mainali-portfolio/",
            footer_note="If you have already spoken to our team, you can ignore this email."
        )