import urllib.request
import json
import os
import re
import psutil
from subprocess import run
from dataclasses import dataclass, field


@dataclass
class CheckResults:
    log: str = field(default=None)
    success: bool = field(default=None)
    triggering: str = field(default=False)

    def __str__(self):
        # outcome as pass/fail/error ("triggering" / "not triggering" / "raising exception")
        if self.success and not self.triggering:
            outcome_str = "PASS"
        elif self.success and self.triggering:
            outcome_str = "FAIL"
        else:
            outcome_str = "ERROR"
        # log: if exception, split class and message
        if isinstance(self.log, Exception):
            # exceptions from subprocess have an useful stderr attribute, try to include that
            try:
                log_str = "{}: {}, stderr: {}".format(
                    str(self.log.__class__),
                    self.log.args[0],
                    self.log.stderr)
            except AttributeError:
                log_str = "{}: {}".format(
                    str(self.log.__class__),
                    self.log.args[0])
        else:
            log_str = str(self.log)
        return "{}\n{}".format(outcome_str, log_str)


def _log_exception(exception) -> CheckResults:
    """
    To be called when a check call catches an exception:
    return a CheckResults instance with log=exception
    """
    return CheckResults(log=exception, success=False, triggering=None)


def mock(return_value=None, return_trigger=False, always_fail=False) -> CheckResults:
    """
    This check always returns the provided 'return_value' (default: None),
    triggering as provided in 'return_trigger' (default: False)
    """
    if not always_fail:
        log = return_value
        success = True
        triggering = return_trigger
        return CheckResults(log, success, triggering)
    else:
        return _log_exception(
            Exception("Mock test set to always fail"))


def _url_request(url, decode=False, encoding=None):
    """
    Wraps call to urllib.request.Request
    """
    req = urllib.request.Request(url)
    urlopen_return = urllib.request.urlopen(req).read()
    if decode:
        urlopen_return = urlopen_return.decode(encoding)
    return urlopen_return


def url_request(url, trigger_if_contains=None, decode=True, encoding='utf-8') -> CheckResults:
    """
    Log the output of a request to 'url',
    optionally trigger if the regex in 'trigger_if_contains' returns a match
    """
    try:
        log = _url_request(url=url, decode=decode, encoding=encoding)
        success = True
        if trigger_if_contains is not None:
            triggering = re.search(pattern=trigger_if_contains, string=log) is not None
        else:
            triggering = False
        return CheckResults(log, success, triggering)
    except Exception as e:
        return _log_exception(e)


def url_json(url) -> CheckResults:
    """
    Log the json-parsed output of a request to 'url'
    Room for enhancement: implement trigger, e.g. matching regex in returned contents
    """
    try:
        log = json.loads(_url_request(url=url))
        success = True
        return CheckResults(log, success)
    except Exception as e:
        return _log_exception(e)


def system_load(max_load=None) -> CheckResults:
    """
    Get system load averages, keep only the 1-minute average
    Optionally trigger if larger than max_load
    If max_load is < 0: use os.cpu_count
    """
    try:
        log = os.getloadavg()[0]
        success = True
        if max_load is not None:
            if max_load < 0:
                max_load = os.cpu_count()
            triggering = log > max_load
        else:
            triggering = False
        return CheckResults(log, success, triggering)
    except Exception as e:
        return _log_exception(e)


def shell(shell_command, timeout_seconds=None) -> CheckResults:
    """
    Generic call to 'shell_command'
    """
    try:
        # should we have no choice in version and 3.5<=python<3.7:
        #   no 'capture_output', so pass stdout=subprocess.PIPE
        #   and 'universal_newlines=True' instead of 'text=True'
        shell_output = run(
            shell_command, text=True, check=True, shell=True,
            capture_output=True, timeout=timeout_seconds)
        return CheckResults(log=shell_output.stdout, success=True)
    except Exception as e:
        return _log_exception(e)


def lsof_count(**kwargs) -> CheckResults:
    """
    Count open files
    """
    # redirection of stderr, otherwise wc also counts that
    return shell(shell_command="lsof 2>/dev/null | wc -l", **kwargs)


def ps_count(include_threads=True, **kwargs) -> CheckResults:
    """
    Count open processes (including threads, by default)
    """
    ps_threads_options = ""
    if include_threads:
        ps_threads_options = "L"
    ps_call = "ps -A{} --no-headers".format(ps_threads_options)
    shell_command = "{} | wc -l".format(ps_call)
    return shell(shell_command=shell_command, **kwargs)


def pgrep_count(pattern, **kwargs) -> CheckResults:
    """
    Count open processes with name matching 'pattern'
    """
    shell_command = "pgrep --count -- {} | wc -l".format(pattern)
    return shell(shell_command=shell_command, **kwargs)


def df(mountpoint=None, options="-hT", **kwargs) -> CheckResults:
    """
    Call 'df' on provided 'mountpoint' (or on all, if no mountpoint is provided)
    """
    # enhancement: parse output (option for machine-readable output?)
    shell_command = "df {} --".format(options)
    if mountpoint is not None:
        shell_command += " {}".format(mountpoint)
    return shell(shell_command=shell_command, **kwargs)


def process_count() -> CheckResults:
    """
    Process count, via psutil.pids
    This is a duplicate of the functionality provided by check 'ps_count' (via shell)
    """
    try:
        nprocesses = len(psutil.pids())
        return CheckResults(log=nprocesses, success=True)
    except Exception as e:
        return _log_exception(e)


def memory_usage() -> CheckResults:
    """
    Memory usage, via psutil.virtual_memory
    """
    try:
        mem_usage = psutil.virtual_memory()
        mem_usage_human = {}
        for f in mem_usage._fields:
            if f != 'percent':
                mem_usage_human[f] = psutil._common.bytes2human(getattr(mem_usage, f))
            else:
                mem_usage_human[f] = "{}%".format(getattr(mem_usage, f))
        return CheckResults(log=mem_usage_human, success=True)
    except Exception as e:
        return _log_exception(e)


def squeue(**kwargs) -> CheckResults:
    """
    Call SLURM 'squeue'
    """
    squeue_call = "squeue"
    return shell(shell_command=squeue_call, **kwargs)
