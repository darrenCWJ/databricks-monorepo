"""Email notification utilities.

Uses Amazon SES SMTP. Requires a get_secret callable for credentials.
"""

import smtplib
from collections.abc import Callable
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    *,
    get_secret: Callable[[str, str], str],
) -> None:
    """Send HTML email via Amazon SES SMTP.

    Args:
        sender_email: Sender email address.
        recipient_email: Recipient email address.
        subject: Email subject line.
        body: HTML content of the email body.
        get_secret: Callable that takes (scope, key) and returns the secret value.
                    In notebooks: pass dbutils.secrets.get
                    In tests: pass a stub function.

    Raises:
        Exception: If sending fails.
    """
    smtp_server = "email-smtp.ap-southeast-1.amazonaws.com"
    smtp_port = 587

    ses_username = get_secret("cdo_aws_ses", "ses_username")
    ses_password = get_secret("cdo_aws_ses", "ses_password")

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(ses_username, ses_password)

        try:
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = recipient_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html"))
            server.send_message(msg)
            print(f"Email sent successfully to {recipient_email}")
        except Exception as e:
            print(f"Error sending to {recipient_email}: {str(e)}")
            raise Exception("An error occurred in sending email\!") from e
