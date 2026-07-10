import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)

APP_URL = "https://suyog12.github.io/suyog-mainali-portfolio/"
SUPPORT_URL = "https://suyog12.github.io/suyog-mainali-portfolio/"
BRAND_COLOR = "#4F46E5"
BRAND_NAME = "Service by SSRM"


# Base HTML template 

def _build_html(
    heading: str,
    body_html: str,
    cta_text: str = None,
    cta_url: str = None,
    footer_note: str = None,
) -> str:
    cta_block = ""
    if cta_text and cta_url:
        cta_block = f"""
        <tr>
            <td align="center" style="padding: 24px 0 8px;">
                <a href="{cta_url}"
                   style="display:inline-block; background-color:{BRAND_COLOR}; color:#ffffff;
                          font-size:15px; font-weight:600; text-decoration:none;
                          padding:13px 32px; border-radius:6px; letter-spacing:0.3px;">
                    {cta_text}
                </a>
            </td>
        </tr>"""

    footer_note_block = ""
    if footer_note:
        footer_note_block = f"""
        <tr>
            <td style="padding: 16px 0 0; color:#9CA3AF; font-size:12px; line-height:1.6;">
                {footer_note}
            </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{heading}</title>
</head>
<body style="margin:0; padding:0; background-color:#F3F4F6; font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F3F4F6; padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px; width:100%; background:#ffffff;
                      border-radius:10px; overflow:hidden;
                      box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background-color:{BRAND_COLOR}; padding:28px 40px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="color:#ffffff; font-size:20px; font-weight:700;
                                 letter-spacing:0.5px;">{BRAND_NAME}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 0;">
              <table width="100%" cellpadding="0" cellspacing="0">

                <!-- Heading -->
                <tr>
                  <td style="padding-bottom:20px;">
                    <h1 style="margin:0; font-size:22px; font-weight:700;
                               color:#111827; line-height:1.3;">
                      {heading}
                    </h1>
                  </td>
                </tr>

                <!-- Body content -->
                <tr>
                  <td style="color:#374151; font-size:15px; line-height:1.7;">
                    {body_html}
                  </td>
                </tr>

                <!-- CTA -->
                {cta_block}

                <!-- Footer note -->
                {footer_note_block}

              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:32px 40px; border-top:1px solid #E5E7EB; margin-top:24px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="color:#6B7280; font-size:13px; line-height:1.6;">
                    <strong style="color:#374151;">{BRAND_NAME}</strong><br/>
                    Nepal&apos;s hospitality management platform<br/>
                    <a href="{SUPPORT_URL}"
                       style="color:{BRAND_COLOR}; text-decoration:none;">
                      Visit our website
                    </a>
                    &nbsp;&middot;&nbsp;
                    <a href="mailto:support@servicebyssrm.com"
                       style="color:{BRAND_COLOR}; text-decoration:none;">
                      support@servicebyssrm.com
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# Info box helper 

def _info_box(rows: list[tuple[str, str]]) -> str:
    """Renders a styled key-value info box. rows = [(label, value), ...]"""
    cells = ""
    for label, value in rows:
        cells += f"""
        <tr>
          <td style="padding:8px 16px; color:#6B7280; font-size:13px;
                     font-weight:600; white-space:nowrap; width:1%;">
            {label}
          </td>
          <td style="padding:8px 16px; color:#111827; font-size:14px;">
            {value}
          </td>
        </tr>"""
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#F9FAFB; border:1px solid #E5E7EB;
                  border-radius:8px; margin:20px 0;">
      {cells}
    </table>"""


# Transport 

def _send(message: MIMEMultipart, to_email: str) -> bool:
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, message.as_string())
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def _make_message(to_email: str, subject: str, html: str) -> MIMEMultipart:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to_email
    message.attach(MIMEText(html, "html"))
    return message


# Staff welcome email 

def send_welcome_email(
    to_email: str,
    full_name: str,
    temp_password: str,
    business_name: str
) -> bool:
    body = f"""
    <p>Hi {full_name},</p>
    <p>
        You have been added as a staff member on <strong>{business_name}</strong>
        via <strong>{BRAND_NAME}</strong>. Your account is ready to use.
    </p>
    {_info_box([
        ("Business", business_name),
        ("Login Email", to_email),
        ("Temporary Password", f"<code style='font-size:16px; letter-spacing:2px; background:#F3F4F6; padding:2px 8px; border-radius:4px;'>{temp_password}</code>"),
    ])}
    <p>
        You must set a new password the first time you log in.
        Click the button below to get started.
    </p>"""

    html = _build_html(
        heading=f"Welcome to {business_name}",
        body_html=body,
        cta_text="Set Your Password",
        cta_url=f"{APP_URL}/change-password",
        footer_note="If you did not expect this email, please contact your manager."
    )
    return _send(_make_message(to_email, f"Your account on {business_name} is ready", html), to_email)


# Password reset email 

def send_password_reset_email(
    to_email: str,
    full_name: str,
    reset_token: str,
    business_name: str
) -> bool:
    reset_url = f"{APP_URL}/reset-password?token={reset_token}"

    body = f"""
    <p>Hi {full_name},</p>
    <p>
        We received a request to reset your password for your account at
        <strong>{business_name}</strong> on {BRAND_NAME}.
    </p>
    <p>
        Click the button below to reset your password.
        This link is valid for <strong>30 minutes</strong>.
    </p>
    {_info_box([
        ("Business", business_name),
        ("Account Email", to_email),
        ("Link expires in", "30 minutes"),
    ])}"""

    html = _build_html(
        heading="Reset Your Password",
        body_html=body,
        cta_text="Reset Password",
        cta_url=reset_url,
        footer_note="If you did not request a password reset, you can safely ignore this email. Your password will not change."
    )
    return _send(_make_message(to_email, "Password reset request for your account", html), to_email)


# Registration confirmation email 

def send_registration_confirmation_email(
    to_email: str,
    full_name: str,
    business_name: str,
    business_slug: str
) -> bool:
    body = f"""
    <p>Hi {full_name},</p>
    <p>
        Your business has been successfully registered on <strong>{BRAND_NAME}</strong>.
        Your account is active and your 14-day free trial has started on the Pro plan.
    </p>
    {_info_box([
        ("Business Name", business_name),
        ("Login Email", to_email),
        ("Business Slug", business_slug),
        ("Trial Plan", "Pro (14 days)"),
    ])}
    <p>
        Log in to your dashboard to set up your outlets, add staff, and start
        managing your operations.
    </p>"""

    html = _build_html(
        heading=f"{business_name} is ready",
        body_html=body,
        cta_text="Go to Dashboard",
        cta_url=f"{APP_URL}/login",
        footer_note=f"Your free trial runs for 14 days. You can renew from Settings &gt; Subscription at any time."
    )
    return _send(_make_message(
        to_email,
        f"Welcome to {BRAND_NAME} — {business_name} is registered",
        html
    ), to_email)


# Generic subscription HTML email 
# Used by subscription_service for all scheduler and payment emails.

async def send_subscription_email(
    to: str,
    subject: str,
    heading: str,
    body_html: str,
    cta_text: str = None,
    cta_url: str = None,
    footer_note: str = None,
) -> bool:
    html = _build_html(
        heading=heading,
        body_html=body_html,
        cta_text=cta_text,
        cta_url=cta_url,
        footer_note=footer_note,
    )
    msg = _make_message(to, subject, html)
    return _send(msg, to)


# Legacy plain-text send_email (kept for backward compatibility) 

async def send_email(to: str, subject: str, body: str) -> bool:
    """Legacy plain-text send. Use send_subscription_email for new code."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to
    message.attach(MIMEText(body, "plain"))
    return _send(message, to)