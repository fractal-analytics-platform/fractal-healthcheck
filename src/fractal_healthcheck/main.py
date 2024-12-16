#!/usr/bin/env python

import click
import yaml
import logging
import os
import sys
from datetime import datetime, timedelta
import textwrap
import smtplib
from email.message import EmailMessage
from dataclasses import dataclass
from fractal_healthcheck import checks
from typing import Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class MailSettings:
    smtp_server: str
    sender: str
    recipients: list[str]
    port: int
    password: str
    instance_name: str


class LastMailStatus:
    """
    Record when the last email was sent.
    Currently: record only 'last' - it reflects some choices
    from a multiple-timestamp scheme, which we may need later on.
    """

    def __init__(self, last=None, last_trigger=None):
        self.last = self._update(timestamp=last)

    @classmethod
    def from_yaml(cls, in_yaml):
        """
        in_yaml: anything that yaml.safe_load can parse (str, open file object, ...)
        """
        loaded = yaml.safe_load(in_yaml)
        # in_yaml may be empty
        if loaded is not None:
            return cls(last=loaded.get("last", None))
        else:
            return cls()

    def to_yaml(self, out_yaml):
        """
        out_yaml: anything that yaml.safe_dump can return to (str, open file object, ...)
        """
        yaml.safe_dump({"last": self.last})

    def _update(self, timestamp=None):
        """
        Update a timestamp field
        no timestamp -> zero epoch (to always trigger a send)
        """
        if timestamp is not None:
            return timestamp
        else:
            return datetime.fromtimestamp(0)

    def update(self):
        """
        Update the timestamp(s) in a status instance
        """
        self.last = self._update(timestamp=datetime.now())
        return self


class Check:
    def __init__(self, function, args=[], kwargs={}):
        self._function = function
        self._kwargs = kwargs
        self.results = checks.CheckResults()

    @classmethod
    def from_function_name(cls, check_function_name, kwargs={}):
        function = getattr(checks, check_function_name)
        return cls(function=function, kwargs=kwargs)

    def run(self):
        self.results = self._function(**self._kwargs)


class CheckSuite:
    def __init__(self, checks):
        self._checks = checks

    @classmethod
    def from_dict(cls, config):
        checks = {}
        for check_name, check_dict in config.items():
            check_function_name = check_dict["function"]
            kwargs = check_dict.get("kwargs", {})
            checks[check_name] = Check.from_function_name(
                check_function_name=check_function_name, kwargs=kwargs
            )

        return cls(checks=checks)

    def run_checks(self, verbose=False):
        for key, check in self._checks.items():
            logger.info("Running check '{}'".format(key))
            check.run()

    def _any(self, field, negate=False):
        """
        any on each 'field' of checks, with early return
        """
        for check in self._checks.values():
            value = getattr(check.results, field)
            if (not negate and value) or (negate and not value):
                return True
        return False

    def any_triggering(self):
        """
        True if any check returned triggering=True
        """
        return self._any(field="triggering")

    def any_failing(self):
        """
        True if any check returned success=False
        """
        return self._any(field="success", negate=True)

    def get_results(self, filter=None):
        """
        Return the results as a dict: {name:check.results}
        Optionally provide a filter in the form ('field', 'value')
        e.g. filter=('triggering', 'True')
        """
        if filter is None:
            return {name: check.results for name, check in self._checks.items()}
        else:
            field, value = filter
            return {
                name: check.results
                for name, check in self._checks.items()
                if getattr(check.results, field) == value
            }


def load_checks(
    yaml_file: str,
) -> tuple[dict[str, Any], dict[str, Any], Optional[MailSettings]]:
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)
    checks_config = config["checks"]
    monitoring_config = config["monitoring"]
    status_file = monitoring_config.get("status_file")
    if status_file is None:
        raise ValueError("Settings: 'monitoring: status_file' is not nullable")

    mail_to = config["monitoring"].get("mail_to", [])
    if len(mail_to) > 0:
        mail_settings = MailSettings(
            recipients=mail_to, **monitoring_config.get("mail_settings", {})
        )
    else:
        mail_settings = None

    return checks_config, monitoring_config, mail_settings


def run_checks(
    *,
    checks_config: dict[str, Any],
    monitoring_config: dict[str, Any],
    mail_settings: Optional[MailSettings] = None,
    output_file: Optional[str] = None,
    send_mail: bool = False,
):
    # Extract useful variables from configs
    status_file = monitoring_config.get("status_file")
    send_mail = send_mail and (mail_settings is not None)
    intervals_hours = {
        "not_triggering": timedelta(
            hours=monitoring_config["intervals_hours"]["not_triggering"]
        ),
        "when_triggering": timedelta(
            hours=monitoring_config["intervals_hours"]["when_triggering"]
        ),
    }

    # Log
    logger.info(f"Status file: '{status_file}'")
    if output_file is not None:
        logger.info(f"Output file: '{output_file}'")

    # Load checks
    check_suite = CheckSuite.from_dict(config=checks_config)

    # Run checks
    logger.info("Checks: started")
    check_suite.run_checks()
    any_triggering = check_suite.any_triggering()
    any_failing = check_suite.any_failing()
    logger.info("Checks: finished")

    # verbose output of checks (debug purposes)
    logger.debug("Print-out of results begins")
    for key, value in check_suite.get_results().items():
        # 2-space-indented printout of check results, for clarity
        logger.debug(
            "Results of check '{}':\n  {}".format(key, str(value).replace("\n", "\n  "))
        )
    logger.debug("Print-out of results ends")

    # manage the "send report?" criteria
    # nothing to report: return None in output_file, output_mails
    status = None
    reason = None
    # reason string, to be used in mail subject: pretty-printed state of send reason, any_triggering, any_failing
    if send_mail:
        if not os.path.isfile(status_file):
            # no status file -> init, always report
            logger.debug(f"Status_file='{status_file}' not found, will initialize.")
            status = LastMailStatus()
            reason = (
                f"First report (triggering: {any_triggering}, failing: {any_failing})"
            )
        else:
            # status file exists -> read latest and check if enough time has passed
            with open(status_file, "r") as f:
                status = LastMailStatus.from_yaml(f)

            since_last = datetime.now() - status.last

            if status.last == datetime.fromtimestamp(0):
                logger.debug("last sent report: never")
            else:
                logger.debug(f"last sent report: {status.last} ({since_last} ago)")

            if any_triggering or any_failing:
                if since_last > intervals_hours["when_triggering"]:
                    logger.debug(
                        "will send email, reason: triggering and enough time elapsed"
                    )
                    reason = f"triggering: {any_triggering}, failing: {any_failing}"
                else:
                    logger.debug(
                        "will not send, reason: triggering, but not enough time elapsed"
                    )
                    send_mail = False
            else:
                if since_last > intervals_hours["not_triggering"]:
                    logger.debug(
                        "will send email, reason: not triggering, but enough time elapsed"
                    )
                    reason = "all ok"
                else:
                    logger.debug(
                        "will not send email, reason: not triggering and not enough time elapsed"
                    )
                    send_mail = False

    return (
        check_suite,
        dict(
            send_mail=send_mail,
            reason=reason,
            status=status,
        ),
    )


def prepare_report(check_suite):
    """
    Format the results in a CheckSuite instance to a string.

    Also reports the number of triggering and not succeeding checks.
    Apart from this, for the moment being this does not expect any schema in 'results_dict',
    it simply wraps string concatenation as "key: str(value)"

    Formatting is minimal. Since a newline at the end of a check output is not ensured,
    one is always added before a check. Then we strip duplicate newlines.
    Indent is added, for readability.
    """

    report_timestamp = "Checks report [{}]".format(datetime.now())

    # Filtering triggering, failing, count them and print a list
    triggering = check_suite.get_results(filter=("triggering", True))
    failing = check_suite.get_results(filter=("success", False))

    msg_triggering = " Checks that set off triggers: {}\n".format(len(triggering))
    msg_triggering += textwrap.indent("\n".join(triggering.keys()), "  ")

    msg_failing = " Checks that failed: {}\n".format(len(failing))
    msg_failing += textwrap.indent("\n".join(failing.keys()), "  ")

    report = " Output of all checks:"
    for name, check in check_suite.get_results().items():
        report += "\n  Check: '{}'\n".format(name)
        report += textwrap.indent(str(check), "   ")

    full_report = "\n".join([report_timestamp, msg_triggering, msg_failing, report])

    # strip duplicate newlines
    full_report = "".join(
        [s for s in full_report.strip().splitlines(True) if s.strip()]
    )

    full_report += "\nEnd of report\n"

    return full_report


def report_to_file(report, filename, mode="a"):
    """
    Wraps: write what prepare_report returns to a file.
      'mode': passed to mode argument of open()
    """
    with open(filename, mode) as file:
        file.write(report)


def report_to_mail(report, reason, mail_settings: MailSettings, mail_backend="smtplib"):
    """
    Wraps: send what prepare_report returns to a list of email addresses
    """
    if mail_backend != "smtplib":
        raise NotImplementedError(f"Invalid {mail_backend=}")

    msg = EmailMessage()
    msg.set_content(report)
    msg["From"] = mail_settings.sender
    msg["To"] = ",".join(mail_settings.recipients)
    msg["Subject"] = "fractal-healthchecks {}: {}".format(
        mail_settings.instance_name, reason
    )

    with smtplib.SMTP(mail_settings.smtp_server, mail_settings.port) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.ehlo()
        server.login(
            user=mail_settings.sender,
            password=mail_settings.password,
            initial_response_ok=True,
        )
        server.ehlo()
        server.sendmail(
            from_addr=mail_settings.sender,
            to_addrs=mail_list,
            msg=msg.as_string(),
        )
        logger.info("Email sent!")


@click.command()
@click.argument("yaml_file", type=click.Path(exists=True))
@click.option(
    "-l",
    "--log-level",
    "log_level",
    type=click.STRING,
    default="INFO",
    help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option(
    "-o",
    "--output-file",
    "output_file",
    type=click.STRING,
    help="Append output (also) to this file",
)
@click.option(
    "-s",
    "--send-mail",
    "send_mail",
    default=False,
    is_flag=True,
    help="Send mails (according to mail_to provided in yaml_file)",
)
def main(
    yaml_file: str,
    log_level: Optional[str] = None,
    output_file: Optional[str] = None,
    send_mail: bool = False,
):
    # Setup logging config
    logging.basicConfig(
        format="[%(asctime)s] %(filename)s: %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=log_level,
    )

    checks_config, monitoring_config, mail_settings = load_checks(yaml_file)
    check_suite, mail_info = run_checks(
        checks_config=checks_config,
        monitoring_config=monitoring_config,
        mail_settings=mail_settings,
        output_file=output_file,
        send_mail=send_mail,
    )
    report = prepare_report(check_suite)
    if output_file is not None:
        report_to_file(report=report, filename=output_file)
    if mail_info.get("send_mail", False):
        report_to_mail(
            report=report,
            reason=mail_info.get("reason"),
            mail_settings=mail_settings,
        )
        status_file = monitoring_config.get("status_file")
        with open(status_file, "w") as file:
            mail_info["status"].update().to_yaml(file)

    return 0


if __name__ == "__main__":
    sys.exit(main())