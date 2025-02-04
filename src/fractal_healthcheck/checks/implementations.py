import json
import os
import psutil
import subprocess
import logging
import shlex
import paramiko
from urllib3.util import Retry
from urllib3 import PoolManager
from fractal_healthcheck.checks.CheckResults import CheckResult


def failing_result(exception: Exception) -> CheckResult:
    """
    To be called when a check call catches an exception:
    return a CheckResults instance with log=exception
    """
    return CheckResult(
        log="",
        exception=exception,
        success=False,
        triggering=False,
    )


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
        return failing_result(exception=e)


def url_json(url: str) -> CheckResult:
    """
    Log the json-parsed output of a request to 'url'
    Room for enhancement: implement trigger, e.g. matching regex in returned contents
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
            return CheckResult(log=log, triggering=True)
    except Exception as e:
        return failing_result(exception=e)


def system_load(max_load: float | None = None) -> CheckResult:
    """
    Get system load averages, keep only the 1-minute average
    Optionally trigger if larger than max_load
    If max_load is < 0: use os.cpu_count
    """
    try:
        load = os.getloadavg()[0]
        if max_load is None or max_load < 0:
            max_load = os.cpu_count()
        triggering = load > max_load
        log = f"System load: {load}"
        return CheckResult(log=log, triggering=triggering)
    except Exception as e:
        return failing_result(exception=e)


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
        return failing_result(exception=e)


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
        return failing_result(e)


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
        return failing_result(exception=e)


def df(
    mountpoint: str | None = None,
    timeout_seconds: int = 60,
) -> CheckResult:
    """
    Call 'df' on provided 'mountpoint' (or on all, if no mountpoint is provided)

    TODO: parse output (option for machine-readable output?)
    """
    command = "df -hT"
    if mountpoint is not None:
        command = f"{command} {mountpoint}"

    try:
        res = subprocess.run(
            shlex.split(command),
            check=True,
            capture_output=True,
            timeout=timeout_seconds,
            encoding="utf-8",
        )
        return CheckResult(log=res.stdout)
    except Exception as e:
        return failing_result(exception=e)


def memory_usage() -> CheckResult:
    """
    Memory usage, via psutil.virtual_memory
    """
    try:
        mem_usage = psutil.virtual_memory()
        mem_usage_human = {}
        for f in mem_usage._fields:
            if f != "percent":
                mem_usage_human[f] = psutil._common.bytes2human(getattr(mem_usage, f))
            else:
                mem_usage_human[f] = f"{getattr(mem_usage, f)}%"
        return CheckResult(log=json.dumps(mem_usage_human, indent=2))
    except Exception as e:
        return failing_result(e)


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
        return failing_result(exception=e)


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
                log=f"Returncode={res2.returncode} for {cmd=}.",
                triggering=False,
            )
        else:
            critical_lines_joined = "\n".join(critical_lines)
            log = f"{target_words=}.\nMatching log lines:\n{critical_lines_joined}"
            return CheckResult(log=log, triggering=True)
    except Exception as e:
        return failing_result(exception=e)


def ssh_on_server(username: str, host: str, pk_path: str):
    pkey = paramiko.RSAKey.from_private_key_file(pk_path)
    client = paramiko.SSHClient()
    policy = paramiko.AutoAddPolicy()
    client.set_missing_host_key_policy(policy)
    try:
        client.connect(host, username=username, pkey=pkey)
        return CheckResult(
            log=(f"Connection to {host} as {username}" "with pk={pk_path}")
        )
    except Exception as e:
        return failing_result(exception=e)
    finally:
        client.close()
