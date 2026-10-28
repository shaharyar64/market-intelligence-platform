import boto3
from pathlib import Path

from gateway.app.core.config import get_settings

settings = get_settings()

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _ses_client():
    return boto3.client(
        "ses",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def send_reset_password_email(email: str, reset_link: str) -> None:
    html = (_TEMPLATES_DIR / "reset_password.html").read_text(encoding="utf-8")
    html = html.replace("{email}", email).replace("{reset_link}", reset_link)

    _ses_client().send_email(
        Source=settings.SES_FROM_EMAIL,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": "Reset your password — Analytics Platform", "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html, "Charset": "UTF-8"},
                "Text": {"Data": f"Reset your password: {reset_link}\n\nExpires in 1 hour.", "Charset": "UTF-8"},
            },
        },
    )


def send_invite_email(email: str, full_name: str, setup_link: str) -> None:
    html = (_TEMPLATES_DIR / "invite_user.html").read_text(encoding="utf-8")
    html = html.replace("{full_name}", full_name).replace("{setup_link}", setup_link)

    _ses_client().send_email(
        Source=settings.SES_FROM_EMAIL,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": "You're invited to Analytics Platform Dashboard", "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html, "Charset": "UTF-8"},
                "Text": {"Data": f"Hi {full_name},\n\nSet up your password here: {setup_link}\n\nExpires in 24 hours.", "Charset": "UTF-8"},
            },
        },
    )
