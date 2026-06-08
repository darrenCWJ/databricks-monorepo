import calendar
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from databricks.sdk.runtime import *


def print_success_or_error(response, message, error_keys=[]):
    status_code = str(response.status_code)
    if status_code.startswith("2"):
        print(f"[HTTP {status_code}] {message}")
    else:
        try:
            error_message = response.json()
            for key in error_keys:
                error_message = error_message[key]
        except:
            error_message = response.text
        print(f"[HTTP {status_code}] {error_message}")


### Validating email addresses
def is_valid_email(email):
    """Function to validate email address.

    Args:
        email (str): email address

    Returns:
        bool: True or False
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    if re.match(pattern, email):
        return True
    else:
        return False


### CustomResponse to replace request response when it is not available
class CustomResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


### Use for validation and modification of string
def validate_group_name(group_name: str) -> str:
    """Function to validate and convert group name to the correct naming convention.

    Args:
        group_name (str): group name

    Returns:
        str: group_name that follow naming convention and all in lower case
    """
    group_name = group_name.lower()

    elements = group_name.split("_")

    # if len(elements) != 4:
    #     raise ValueError("Group name must follow naming convention of {env}_{project}_{schema}_{table}")

    # if elements[0] not in ['dev', 'uat', 'stg', 'prd']:
    #     raise ValueError("First element of the group name must be 'dev', 'uat', 'stg', or 'prd'")

    return group_name


### Send SMTP email
def send_email(
    sender_email,
    subject,
    body,
    to_emails=[],
    cc_emails=[],
    bcc_emails=[],
    blind_email=False,
    **kwargs,
):
    """
    Send email using Amazon SES SMTP

    Parameters:
    sender_email (str): Email address of sender
    subject (str): Email subject
    body (str): HTML content of the email
    to_emails (list): Email address of direct recipient(s)
    cc_emails (list): Email address of carbon copy recipient(s)
    bcc_emails (list): Email address of blind carbon copy recipient(s)
    blind_email (boolean): Indicate if this is a mass email blast
    **kwargs: Additional email headers
    """
    # our SES is in internet UAT account 761391519975
    # PRD/DEV Shared Cluster cannot be used to send emails
    # IMPT: AWS SES has a hard quota of 50 recipients per send_message()
    # There is also a rolling 24-hour limit

    # Amazon SES SMTP credentials
    smtp_server = "email-smtp.ap-southeast-1.amazonaws.com"
    smtp_port = 587

    ses_username = dbutils.secrets.get("cdo_aws_ses", "ses_username")
    ses_password = dbutils.secrets.get("cdo_aws_ses", "ses_password")

    # Create SMTP connection
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(ses_username, ses_password)

        try:
            # send to recipients individually if sending mass bcc email
            if blind_email:
                for user in bcc_emails:
                    # Create email message
                    msg = MIMEMultipart()
                    msg["From"] = sender_email
                    msg["To"] = user
                    if cc_emails:
                        msg["Cc"] = ", ".join(cc_emails)
                    msg["Subject"] = subject
                    for key, value in kwargs.items():
                        msg[key] = value
                    msg.attach(MIMEText(body, "html"))
                    server.send_message(msg)
                    print(f"BCC email sent successfully to {user}")
            else:
                # Create email message
                msg = MIMEMultipart()
                msg["From"] = sender_email
                if to_emails:
                    msg["To"] = ", ".join(to_emails)
                if bcc_emails:
                    msg["Bcc"] = ", ".join(bcc_emails)
                msg["Subject"] = subject
                for key, value in kwargs.items():
                    msg[key] = value

                msg.attach(MIMEText(body, "html"))
                server.send_message(msg)
                print(
                    f"Email sent successfully TO: {to_emails}, CC: {cc_emails}, BCC: {bcc_emails}"
                )

        except Exception as e:
            print(f"Error sending to {to_emails}: {str(e)}")
            raise Exception("An error occurred in sending email!")
