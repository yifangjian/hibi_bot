import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("hibi_bot.email_client")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_notification_email(subject: str, body: str) -> None:
    """用 Gmail SMTP（應用程式密碼）寄一封通知信給 settings.notify_email。呼叫端應該把
    這個包在 try/except 裡：寄信失敗不該影響任何使用者互動流程，這只是給研究者的輔助通知。
    """
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = settings.gmail_address
    message["To"] = settings.notify_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(settings.gmail_address, settings.gmail_app_password)
        server.send_message(message)
