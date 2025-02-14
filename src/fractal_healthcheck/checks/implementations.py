import json
import psutil
import subprocess
import logging
import shlex
from typing import Optional
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


def system_load(max_load_fraction: float = 0.7) -> CheckResult:
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
    max_perc_usage: int = 85,
) -> CheckResult:
    """
    Call psutil.disk_usage on provided 'mountpoint'
    """
    usage_perc = psutil.disk_usage(mountpoint).percent
    tot_disk = round(((psutil.disk_usage(mountpoint).total / 1000) / 1000) / 1000, 2)
    try:
        return CheckResult(
            log=(
                f"The usage of {mountpoint} is {usage_perc}%, while the threshold is "
                f"{max_perc_usage}%.\nTotal disk memory is {tot_disk} GB"
            ),
            success=max_perc_usage > usage_perc,
        )
    except Exception as e:
        return CheckResult(exception=e, success=False)


def memory_usage(max_memory_usage: int = 75) -> CheckResult:
    """
    Memory usage, via psutil.virtual_memory
    """
    try:
        mem_usage = psutil.virtual_memory()

        mem_usage_total = round(
            ((mem_usage.total / 1000) / 1000) / 1000, 2
        )  # GigaBytes
        mem_usage_available = round(((mem_usage.available / 1024) / 1024) / 1024, 2)
        mem_usage_percent = round(mem_usage.percent, 1)
        log = {
            "Total memory": f"{mem_usage_total} GB",
            "Free memory": f"{mem_usage_available} GB",
            "Percent": f"{mem_usage_percent}%",
        }
        return CheckResult(
            log=f"The memory usage is {mem_usage_percent}%, while the threshold is {max_memory_usage}%\n{json.dumps(log, indent=2)}",
            success=max_memory_usage > mem_usage_percent,
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


def ssh_on_server(
    username: str,
    host: str,
    password: Optional[str] = None,
    private_key_path: Optional[str] = None,
    port: int = 22,
) -> CheckResult:
    connection = Connection(
        host=host,
        user=username,
        port=port,
        forward_agent=False,
    )
    if password is not None:
        connection.connect_kwargs.update({"password": password})
    elif private_key_path is not None:
        connection.connect_kwargs.update(
            {
                "key_filename": private_key_path,
                "look_for_keys": False,
            }
        )
    elif password is not None and private_key_path is not None:
        return CheckResult(
            log="Password and private_key_path have a value, remove one of them",
            success=False,
        )
    elif password is None and private_key_path is None:
        return CheckResult(
            log="Password and private_key_path have not a value, choose one of them",
            success=False,
        )
    try:
        with connection as c:
            res = c.run("whoami")
            return CheckResult(
                log=f"Connection to {host} as {username} with private_key={private_key_path} result:\n{res.stdout}",
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
            return CheckResult(log=json.dumps(log, indent=2), success=False)
        else:
            return CheckResult(log=json.dumps(log, indent=2))
    except Exception as e:
        return CheckResult(exception=e, success=False)
