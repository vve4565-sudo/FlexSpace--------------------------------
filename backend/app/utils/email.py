import logging
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config.config import settings

logger = logging.getLogger(__name__)
_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "frontend" / "templates"
_template_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(("html", "xml")),
)


def send_email(to_email: str, subject: str, text: str) -> None:
    if not settings.emails_enabled or not settings.EMAILS_FROM_EMAIL:
        logger.error("Email delivery is not configured")
        raise RuntimeError("Email delivery is not configured")

    email = EmailMessage()
    email["From"] = str(settings.EMAILS_FROM_EMAIL)
    email["To"] = to_email
    email["Subject"] = subject
    email.set_content(text, subtype="html")

    if settings.SMTP_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(email)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(email)
    logger.info("Email sent")


def generate_password_recovery_template(token: str) -> str:
    template = _template_env.get_template("recovery_password_template.html")
    reset_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/auth/reset_password?token={token}"
    return template.render(reset_url=reset_url)


def generate_koworking_template(start_time: str, end_time: str) -> str:
    template = _template_env.get_template("confirm_kaworking.html")
    return template.render(start_time=start_time, end_time=end_time)
