import json
import psutil
import subprocess
import logging
import shlex
from fabric.connection import Connection
from urllib3.util import Retry
from urllib3 import PoolManager
from fractal_healthcheck.checks.CheckResults import CheckResult


def subprocess_run(command: str) -> CheckResult:
    """
    Generic call to `subprocess.run`
    """
    try:
        res = subprocess.run(
            shlex.split(command),
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        return CheckResult(log=res.stdout)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def url_json(url: str) -> CheckResult:
    """
    Log the json-parsed output of a request to 'url'
    Room for enhancement: e.g. matching regex in returned contents
    """
    try:
        retries = Retry(connect=5)
        http = PoolManager(retries=retries)
        response = http.request("GET", url)
        if response.status == 200:
            data = json.loads(response.data.decode("utf-8"))
            log = json.dumps(data, sort_keys=True, indent=2)
            return CheckResult(log=log)
        else:
            log = json.dumps(
                dict(
                    status=response.status,
                    data=response.data.decode("utf-8"),
                ),
                sort_keys=True,
                indent=2,
            )
            return CheckResult(log=log, success=False)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def system_load(max_load_fraction: float) -> CheckResult:
    """
    Get system load averages, keep only the 5-minute average
    """
    load_fraction = psutil.getloadavg()[1] / psutil.cpu_count()

    try:
        log = f"System load: {load_fraction}"
        return CheckResult(log=log, success=max_load_fraction > load_fraction)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def lsof_count() -> CheckResult:
    """
    Count open files via lsof
    """
    try:
        res = subprocess.run(
            shlex.split("lsof -t"),
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        num_lines = len(res.stdout.strip("\n").split("\n"))
        log = f"Number of open files (via lsof): {num_lines}"
        return CheckResult(log=log)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def count_processes() -> CheckResult:
    """
    Process count, via psutil.pids
    This is a duplicate of the functionality provided by check 'ps_count' (via shell)
    """
    try:
        nprocesses = len(psutil.pids())
        log = f"Number of processes (via psutil.pids): {nprocesses}"
        return CheckResult(log=log)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def ps_count_with_threads() -> CheckResult:
    """
    Count open processes (including thread)
    """
    try:
        res = subprocess.run(
            shlex.split("ps -AL --no-headers"),
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        num_lines = len(res.stdout.strip("\n").split("\n"))
        log = f"Number of open processes&threads (via ps -AL): {num_lines}"
        return CheckResult(log=log)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def disk_usage(
    mountpoint: str,
) -> CheckResult:
    """
    Call psutil.disk_usage on provided 'mountpoint'
    """
    max_perc_usage = 85
    usage_perc = psutil.disk_usage(mountpoint).percent
    try:
        return CheckResult(
            log=f"The usage of {mountpoint} is {usage_perc}%, while the threashold is {max_perc_usage}%",
            success=usage_perc > max_perc_usage,
        )
    except Exception as e:
        return CheckResult(exception=e, success=False)


def memory_usage() -> CheckResult:
    """
    Memory usage, via psutil.virtual_memory
    """
    MAX_MEMORY_USAGE = 75
    try:
        mem_usage = psutil.virtual_memory()

        mem_usage_total = round(
            ((mem_usage.total / 1024) / 1024) / 1024, 2
        )  # GigaBytes
        mem_usage_available = round(((mem_usage.available / 1024) / 1024) / 1024, 2)
        mem_usage_percent = round(mem_usage.percent, 1)
        log = {
            "Total memory": f"{mem_usage_total} GB",
            "Free memory": f"{mem_usage_available} GB",
            "Percent": f"{mem_usage_percent} GB",
        }
        return CheckResult(
            log=f"The memory usage is {mem_usage_percent}%, while the threashold is {MAX_MEMORY_USAGE}%\n {json.dumps(log, indent=2)}",
            success=mem_usage_percent > MAX_MEMORY_USAGE,
        )
    except Exception as e:
        return CheckResult(exception=e, success=False)


def check_mounts(mounts: list[str]) -> CheckResult:
    """
    Check the status of the mounted folders
    """
    try:
        paths = " ".join(mounts)
        res = subprocess.run(
            shlex.split(f"ls {paths}"),
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        num_objs = len(res.stdout.strip("\n").split("\n"))
        log = f"Number of files/folders (via ls {paths}): {num_objs}"
        return CheckResult(log=log)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def service_logs(
    service: str, time_interval: str, target_words: list[str], use_user: bool = False
) -> CheckResult:
    """
    Grep for target_words in service logs
    """
    parsed_target_words = "|".join(target_words)
    if use_user:
        cmd = f'journalctl --user -q -u {service} --since "{time_interval}"'
    else:
        cmd = f'journalctl -q -u {service} --since "{time_interval}"'
    try:
        logging.info(f"{cmd=}")

        res1 = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            encoding="utf-8",
        )
        logging.info(f"journalctl returncode: {res1.returncode}")

        cmd = f'grep -E "{parsed_target_words}"'
        logging.info(f"{cmd=}")
        res2 = subprocess.run(
            shlex.split(cmd),
            input=res1.stdout,
            capture_output=True,
            encoding="utf-8",
        )
        critical_lines = res2.stdout.strip("\n").split("\n")
        if res2.returncode == 1:
            return CheckResult(
                log=f"Returncode={res2.returncode} for {cmd=}.", success=True
            )
        else:
            critical_lines_joined = "\n".join(critical_lines)
            log = f"{target_words=}.\nMatching log lines:\n{critical_lines_joined}"
            return CheckResult(log=log, success=False)
    except Exception as e:
        return CheckResult(exception=e, success=False)


def ssh_on_server(username: str, host: str, private_key_path: str) -> CheckResult:
    try:
        with Connection(
            host=host,
            user=username,
            forward_agent=False,
            connect_kwargs={
                "key_filename": private_key_path,
                "look_for_keys": False,
            },
        ) as connection:
            res = connection.run("whoami")
            return CheckResult(
                log=(
                    f"Connection to {host} as {username} with pk={private_key_path} is succeed, result: {res}"
                )
            )
    except Exception as e:
        return CheckResult(
            exception=e,
            success=False,
        )


def service_is_active(services: list[str], use_user: bool = False) -> CheckResult:
    parsed_services = " ".join(services)

    if use_user:
        cmd = f"systemctl is-active --user {parsed_services}"
    else:
        cmd = f"systemctl is-active {parsed_services}"
    try:
        logging.info(f"{cmd=}")
        res = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            encoding="utf-8",
        )
        statuses = res.stdout.split("\n")
        log = dict(zip(services, statuses))
        if "inactive" in res.stdout or "failed" in res.stdout:
            return CheckResult(log=json.dumps(log), success=False)
        else:
            return CheckResult(log=json.dumps(log))
    except Exception as e:
        return CheckResult(exception=e, success=False)
