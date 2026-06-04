import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)


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


def send_welcome_email(
    to_email: str,
    full_name: str,
    temp_password: str,
    business_name: str
) -> bool:
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Welcome to {business_name} — Service by SSRM"
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to_email

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Welcome to {business_name}!</h2>
        <p>Hi {full_name},</p>
        <p>Your account has been created on <strong>Service by SSRM</strong>.</p>
        <p>Here are your login details:</p>
        <table style="background:#f4f4f4; padding:16px; border-radius:8px;">
            <tr><td><strong>Email:</strong></td><td>{to_email}</td></tr>
            <tr><td><strong>Temporary Password:</strong></td><td style="font-size:18px; letter-spacing:2px;">{temp_password}</td></tr>
        </table>
        <br/>
        <p>
            <a href="http://localhost:3000/change-password" style="
                background-color: #4F46E5;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 6px;
                display: inline-block;
                margin-top: 12px;
            ">
                Set Your Password
            </a>
        </p>
        <p style="color:#888; font-size:13px;">
            You must change your password on first login.<br/>
            If you did not expect this email please contact your manager.
        </p>
        <br/>
        <p>— Service by SSRM Team</p>
    </body>
    </html>
    """
    message.attach(MIMEText(html, "html"))
    return _send(message, to_email)


def send_password_reset_email(
    to_email: str,
    full_name: str,
    reset_token: str,
    business_name: str
) -> bool:
    reset_url = f"http://localhost:3000/reset-password?token={reset_token}"

    message = MIMEMultipart("alternative")
    message["Subject"] = "Reset Your Password — Service by SSRM"
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to_email

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Password Reset Request</h2>
        <p>Hi {full_name},</p>
        <p>We received a request to reset your password for your account at <strong>{business_name}</strong>.</p>
        <p>Click the button below to reset your password. This link expires in <strong>30 minutes</strong>.</p>
        <p>
            <a href="{reset_url}" style="
                background-color: #4F46E5;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 6px;
                display: inline-block;
                margin-top: 12px;
            ">
                Reset Password
            </a>
        </p>
        <p style="color:#888; font-size:13px;">
            If you did not request a password reset, ignore this email.<br/>
            Your password will not change until you click the link above.
        </p>
        <br/>
        <p>— Service by SSRM Team</p>
    </body>
    </html>
    """
    message.attach(MIMEText(html, "html"))
    return _send(message, to_email)


def send_registration_confirmation_email(
    to_email: str,
    full_name: str,
    business_name: str,
    business_slug: str
) -> bool:
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Welcome to Service by SSRM — {business_name} is ready"
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to_email

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Your business is ready!</h2>
        <p>Hi {full_name},</p>
        <p>Your business <strong>{business_name}</strong> has been successfully registered on Service by SSRM.</p>
        <table style="background:#f4f4f4; padding:16px; border-radius:8px;">
            <tr><td><strong>Business:</strong></td><td>{business_name}</td></tr>
            <tr><td><strong>Login Email:</strong></td><td>{to_email}</td></tr>
            <tr><td><strong>Slug:</strong></td><td>{business_slug}</td></tr>
        </table>
        <br/>
        <p>
            <a href="http://localhost:3000/login" style="
                background-color: #4F46E5;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 6px;
                display: inline-block;
                margin-top: 12px;
            ">
                Go to Dashboard
            </a>
        </p>
        <br/>
        <p>— Service by SSRM Team</p>
    </body>
    </html>
    """
    message.attach(MIMEText(html, "html"))
    return _send(message, to_email)

async def send_email(to: str, subject: str, body: str) -> bool:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to
    message.attach(MIMEText(body, "plain"))
    return _send(message, to)