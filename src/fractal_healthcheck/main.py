#!/usr/bin/env python

import click
import logging
import sys
import time
from typing import Optional

from fractal_healthcheck import LOGGER_NAME
from fractal_healthcheck.report import load_email_config
from fractal_healthcheck.report import prepare_report
from fractal_healthcheck.report import report_to_file
from fractal_healthcheck.report import report_to_email
from fractal_healthcheck.checks import load_check_suite

logger = logging.getLogger(LOGGER_NAME)


@click.command()
@click.argument(
    "config_file",
    type=click.Path(
        exists=True,
        dir_okay=False,
    ),
)
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
    help="Append report to this text file.",
)
@click.option(
    "-s",
    "--send-mail",
    "send_mail",
    default=False,
    is_flag=True,
    help="Send report by email, if appropriate.",
)
def main(
    config_file: str,
    log_level: str,
    output_file: Optional[str] = None,
    send_mail: bool = False,
):
    # Setup logging config
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=log_level,
    )

    # Load configurations
    checks_suite = load_check_suite(config_file)
    if send_mail:
        email_config = load_email_config(config_file)
        instance_name = email_config.instance_name
    else:
        instance_name = None

    # Run checks and get the checks' execution time
    t_start = time.time()
    checks_suite.run()
    checks_runtime = round(time.time() - t_start, 2)

    # Prepare report
    report = prepare_report(
        checks_suite,
        checks_runtime=checks_runtime,
        instance_name=instance_name,
    )

    # Write report to file
    if output_file is not None:
        report_to_file(report=report, filename=output_file)

    # Send report by email
    if send_mail:
        report_to_email(
            check_suite=checks_suite,
            report=report,
            mail_settings=email_config,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
