from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_review_notification(
    *,
    gmail_user: str,
    gmail_app_password: str,
    recipient: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = gmail_user
    message["To"] = recipient
    message.attach(MIMEText(body_text, "plain"))
    if body_html:
        message.attach(MIMEText(body_html, "html"))

    username = gmail_user.strip()
    password = gmail_app_password.strip().replace(" ", "")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(username, password)
            server.sendmail(username, [recipient], message.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise smtplib.SMTPAuthenticationError(
            exc.smtp_code,
            (
                f"{exc.smtp_error!r}. Gmail rejected the credentials for {username}. "
                "Use a Google App Password (not your normal Gmail password). "
                "Enable 2-Step Verification, then create one at "
                "https://myaccount.google.com/apppasswords"
            ).encode(),
        ) from exc
