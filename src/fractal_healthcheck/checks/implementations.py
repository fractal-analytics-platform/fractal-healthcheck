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
    Log the json-parsed output of a request to 'url'.
    """
    try:
        retries = Retry(connect=5)
        http = PoolManager(retries=retries)
        response_data = None
        response = http.request("GET", url)
        response_data = response.data.decode("utf-8")
        if response.status == 200:
            data = json.loads(response_data)
            log = json.dumps(data, sort_keys=True, indent=2)
            return CheckResult(log=log)
        else:
            log = json.dumps(
                dict(
                    status=response.status,
                    data=response_data,
                ),
                sort_keys=True,
                indent=2,
            )
            return CheckResult(log=log, success=False)
    except Exception as e:
        log = f"Response body:\n{response_data}\nOriginal error:\n{str(e)}"
        return CheckResult(log=log, success=False)


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


def lsof_ssh(max_ssh_lines: int = 32) -> CheckResult:
    """
    Count and print ssh entries in `lsof -i`
    """
    try:
        res = subprocess.run(
            shlex.split("lsof -i"),
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        all_lines = res.stdout.strip("\n").split("\n")
        ssh_lines = [line for line in all_lines if "ssh" in line.lower()]
        log = "\n".join(ssh_lines)
        if len(ssh_lines) > max_ssh_lines:
            log = f"{log}\nNumber of lines exceeds {max_ssh_lines=}."
            return CheckResult(log=log, success=False)
        else:
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


def create_table(headers: list, rows: list, column_widths: list) -> str:
    """
    Create a simple table with headers and rows.
    Args:
        headers: List of column header names
        rows: List of lists containing row data
        column_widths: List of integer widths for each column
    Returns:
        String containing the formatted table
    """
    lines = []
    header_row = " | ".join(
        str(header).ljust(width) for header, width in zip(headers, column_widths)
    )
    lines.append(header_row)
    lines.append("-" * len(header_row))
    for row in rows:
        row_str = " | ".join(
            str(cell or "-").ljust(width) for cell, width in zip(row, column_widths)
        )
        lines.append(row_str)
    return "\n".join(lines)


def postgresql_db_info(
    dbname: str,
    user: Optional[str] = None,
    password: Optional[str] = None,
    host: str = "localhost",
    port: int = 5432,
) -> CheckResult:
    """
    Query a PostgreSQL database to check:
    - Last autovacuum and autoanalyze times
    - Autovacuum/analyze thresholds
    - Table sizes
    """
    import psycopg

    try:
        conn_params = {
            "dbname": dbname,
            "user": user,
            "password": password,
            "host": host,
            "port": port,
        }
        conn_params = {k: v for k, v in conn_params.items() if v is not None}

        connection = psycopg.connect(**conn_params)
        cursor = connection.cursor()

        logs = []

        # First query: autovacuum and autoanalyze status.
        # c.relkin = 'r' means just Regular table (not indexes, not toast ecc.)
        # n.nspname = 'public' means just public tables, not postgres/system tables
        autovacuum_query = """
            SELECT
                c.relname AS table,
                s.n_live_tup,
                s.n_dead_tup,
                s.last_autovacuum,
                s.last_autoanalyze,
                current_setting('autovacuum_vacuum_threshold') AS vacuum_threshold,
                current_setting('autovacuum_analyze_threshold') AS analyze_threshold
            FROM
                pg_class c
            JOIN
                pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN
                pg_stat_user_tables s ON s.relid = c.oid
            WHERE
                c.relkind = 'r' AND n.nspname = 'public'
            ORDER BY
                s.last_autovacuum DESC NULLS LAST;
        """

        cursor.execute(autovacuum_query)
        rows = cursor.fetchall()

        logs.append("== Autovacuum/Autoanalyze Status ==")
        headers = [
            "Table",
            "Live Tuples",
            "Dead Tuples",
            "Last Autovacuum",
            "Last Autoanalyze",
            "Vacuum Thresh.",
            "Analyze Thresh.",
        ]
        column_widths = [34, 11, 11, 32, 32, 14, 14]
        table_rows = [
            [
                row[0],
                row[1],
                row[2],
                str(row[3]),
                str(row[4]),
                row[5],
                row[6],
            ]
            for row in rows
        ]
        logs.append(create_table(headers, table_rows, column_widths))

        # Second query: table size and indexes size.
        # Just a subset of all tables/pk/ix
        table_size_query = """
        SELECT
            c.relname AS table_name,
            pg_size_pretty(pg_table_size(c.oid)) AS table_size,
            pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
            s.n_live_tup AS approx_row_count
        FROM
            pg_class c
        JOIN
            pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN
            pg_stat_user_tables s ON s.relid = c.oid
        WHERE
                (c.relkind = 'r' OR c.relkind = 'i') AND n.nspname = 'public'
        ORDER BY
            pg_total_relation_size(c.oid) DESC
        LIMIT 20;
        """

        cursor.execute(table_size_query)
        rows = cursor.fetchall()

        logs.append("\n== Table Sizes ==")
        headers = ["Table", "Table Size", "Total Size", "Estimated Rows"]
        column_widths = [38, 12, 12, 16]
        table_rows = [[row[0], row[1], row[2], row[3]] for row in rows]
        logs.append(create_table(headers, table_rows, column_widths))

        cursor.close()
        connection.close()

        return CheckResult(
            log="\n".join(logs),
            success=True,
        )

    except Exception as e:
        return CheckResult(log="", success=False, exception=e)
