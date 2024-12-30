import urllib.request
import json
import os
import psutil
import subprocess
import shlex

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


def _url_request(url: str, encoding: str | None = None):
    """
    Wraps call to urllib.request.Request
    """
    urlopen_return = urllib.request.urlopen(url).read()
    if encoding is not None:
        urlopen_return = urlopen_return.decode(encoding)
    return urlopen_return


def url_json(url: str) -> CheckResult:
    """
    Log the json-parsed output of a request to 'url'
    Room for enhancement: implement trigger, e.g. matching regex in returned contents
    """
    try:
        data = json.loads(_url_request(url=url))
        log = json.dumps(data, sort_keys=True, indent=2)
        return CheckResult(log=log)
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
