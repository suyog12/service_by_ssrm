import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings


def send_welcome_email(to_email: str, full_name: str, temp_password: str, business_name: str):
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

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, message.as_string())