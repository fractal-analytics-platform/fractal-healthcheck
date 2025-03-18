import yaml
import logging
from datetime import datetime, timezone, timedelta
import smtplib
from email.message import EmailMessage
import textwrap
from pydantic import BaseModel, Field, EmailStr
from fractal_healthcheck import LOGGER_NAME
import fractal_healthcheck

from fractal_healthcheck.checks import CheckSuite

logger = logging.getLogger(LOGGER_NAME)


class MailSettings(BaseModel):
    smtp_server: str
    smpt_server_port: int
    sender: EmailStr
    include_starttls: bool = True
    include_login: bool = True
    password: str
    recipients: list[EmailStr] = Field(min_length=1)
    status_file: str
    grace_time_not_triggering_hours: int = 72
    grace_time_triggering_hours: int = 4
    instance_name: str


def load_email_config(config_file: str) -> MailSettings:
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    email_config = config["email-config"]
    mail_settings = MailSettings(**email_config)
    return mail_settings


class LastMailStatus:
    """
    Record when the last email was sent.
    Currently: record only 'last' - it reflects some choices
    from a multiple-timestamp scheme, which we may need later on.
    """

    last_email_timestamp: datetime | None

    def __init__(
        self,
        last_email_timestamp: datetime | None = None,
    ):
        self.last_email_timestamp = last_email_timestamp

    @classmethod
    def from_yaml(cls, in_yaml):
        """
        in_yaml: anything that yaml.safe_load can parse (str, open file object, ...)
        """
        loaded = yaml.safe_load(in_yaml)
        # in_yaml may be empty
        if loaded is not None:
            return cls(last_email_timestamp=loaded.get("last_email_timestamp", None))
        else:
            return cls()

    def to_yaml(self, out_yaml):
        """
        out_yaml: anything that yaml.safe_dump can return to (str, open file object, ...)
        """
        yaml.safe_dump({"last_email_timestamp": self.last_email_timestamp}, out_yaml)

    def update(self):
        """
        Set the timestamp to current UTC time.
        """
        self.last_email_timestamp = datetime.now(tz=timezone.utc)
        return self


def prepare_report(
    check_suite: CheckSuite,
    checks_runtime: float,
    instance_name: str | None,
) -> str:
    """
    Format the results in a CheckSuite instance to a string.
    It takes as argument also the time needed to run the checks.

    Also reports the number of not succeeding checks.
    Apart from this, for the moment being this does not expect any schema in 'results_dict',
    it simply wraps string concatenation as "key: str(value)"

    Formatting is minimal. Since a newline at the end of a check output is not ensured,
    one is always added before a check. Then we strip duplicate newlines.
    Indent is added, for readability.

    """

    # Filtering failing and count them and print a list
    failing = check_suite.get_failing_results()
    remaining = check_suite.get_non_failing_results()
    summary = (
        f"# Summary\n\n"
        f"Fractal instance: {instance_name}\n"
        f"Report timestamp: {datetime.now(tz=timezone.utc)}\n"
        f"Fractal-healthcheck version: {fractal_healthcheck.__VERSION__}\n"
        f"Total number of checks: {len(check_suite.checks)}\n"
        f"Number of failed checks: {len(failing)}\n"
        f"Checks Runtime: {checks_runtime} seconds\n"
        "\n"
    )

    msg_failing = textwrap.indent("\n".join(failing.keys()), " * ")
    msg_remaining = textwrap.indent("\n".join(remaining.keys()), " * ")
    recap = (
        "# Recap\n\n"
        "List of failed checks:\n"
        f"{msg_failing}\n"
        "List of successful checks:\n"
        f"{msg_remaining}\n"
        "\n"
    )

    report = "# Detailed report\n\n"
    for name, result in check_suite.get_results().items():
        report += (
            f"Check: {name}\n"
            f"Status: {result.status}\n"
            f"Logs:\n{textwrap.indent(result.full_log, '> ')}\n"
            "----\n\n"
        )
    report = f"{report}End of report\n"

    separator = "-" * 80 + "\n\n"
    full_report = "".join(
        (
            summary,
            separator,
            recap,
            separator,
            report,
            separator,
        )
    )

    return full_report


def report_to_file(report, filename):
    """
    Append report to file.
    """
    logger.info(f"[report_to_file] START - {filename}")
    with open(filename, "a") as f:
        f.write(report)
    logger.info("[report_to_file] END")


def report_to_email(
    *,
    check_suite: CheckSuite,
    report: str,
    mail_settings: MailSettings,
):
    """
    Send report by email.
    """

    logger.info("[report_to_email] START")

    # (1/3) Find out whether email should be sent

    status_file = mail_settings.status_file
    any_failing = check_suite.any_failing

    try:
        with open(mail_settings.status_file, "r") as f:
            last_mail_info = LastMailStatus.from_yaml(f)

        if last_mail_info.last_email_timestamp is None:
            logger.info("[report_to_email] No report email ever sent")
            since_last = datetime.now(tz=timezone.utc) - datetime.fromtimestamp(
                0, tz=timezone.utc
            )
        else:
            since_last = (
                datetime.now(tz=timezone.utc) - last_mail_info.last_email_timestamp
            )
            logger.info(
                f"[report_to_email] Last report email sent on {last_mail_info.last_email_timestamp} ({since_last} ago)"
            )

        if any_failing:
            if since_last > timedelta(hours=mail_settings.grace_time_triggering_hours):
                logger.info(
                    "[report_to_email] Will send email, reason: triggering, and enough time elapsed"
                )
                mail_reason = "WARNING"
            else:
                mail_reason = None
                logger.info(
                    "[report_to_email] Will not send, reason: triggering, but not enough time elapsed"
                )
        else:
            if since_last > timedelta(
                hours=mail_settings.grace_time_not_triggering_hours
            ):
                logger.info(
                    "[report_to_email] Will send email, reason: not failing, but enough time elapsed"
                )
                mail_reason = "ALL OK"
            else:
                mail_reason = None
                logger.info(
                    "[report_to_email] Will not send, reason: not failing, and not enough time elapsed"
                )

    except Exception as e:
        logger.info(
            f"[report_to_email] Cannot read status_file='{status_file}', original error: {e}."
        )
        last_mail_info = LastMailStatus()
        mail_reason = "First report"

    if mail_reason is None:
        logger.info("[report_to_email] Exit.")
        return

    logger.info(f"[report_to_email] I will send an email, with {mail_reason=}")

    # (2/3) Prepare email
    msg = EmailMessage()
    msg["From"] = mail_settings.sender
    msg["To"] = ", ".join(mail_settings.recipients)
    msg["Subject"] = f"[Fractal, {mail_settings.instance_name}] {mail_reason}"
    msg.set_content(report)

    # (3/3) Send email and update timestamp
    with smtplib.SMTP(
        host=mail_settings.smtp_server, port=mail_settings.smpt_server_port
    ) as server:
        server.ehlo()
        if mail_settings.include_starttls:
            server.starttls()
            server.ehlo()
        if mail_settings.include_login:
            server.login(
                user=mail_settings.sender,
                password=mail_settings.password,
                initial_response_ok=True,
            )
            logger.info("[report_to_email] Successful login.")
        else:
            logger.info("[report_to_email] No login attempted.")
        server.sendmail(
            from_addr=mail_settings.sender,
            to_addrs=mail_settings.recipients,
            msg=msg.as_string(),
        )
        logger.info("[report_to_email] Email sent!")
        with open(status_file, "w") as f:
            last_mail_info.update()
            last_mail_info.to_yaml(f)
        logger.info(f"[report_to_email] {status_file} updated")
    logger.info("[report_to_email] END")
