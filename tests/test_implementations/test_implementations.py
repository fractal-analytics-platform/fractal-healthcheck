import json
import subprocess
import psutil
from fractal_healthcheck.checks.implementations import (
    subprocess_run,
    check_mounts,
    system_load,
    url_json,
    lsof_count,
    count_processes,
    ps_count_with_threads,
    disk_usage,
    memory_usage,
    service_logs,
    service_is_active,
)


def test_subprocess_run():
    result = subprocess_run("echo 'Hello, World!'")
    assert result.success
    assert "Hello, World!" in result.log


def test_url_json(monkeypatch):
    def mock_request_200(self, method, url):
        class MockResponse:
            status = 200
            data: bytes = b'{"test": "value"}'

        return MockResponse()

    def mock_request_404(self, method, url):
        class MockResponse:
            status = 404
            data: bytes = b'{"error": "message"}'

        return MockResponse()

    monkeypatch.setattr("urllib3.PoolManager.request", mock_request_200)
    result = url_json("http://example.com/")
    assert result.success
    assert "test" in result.log
    assert "value" in result.log

    monkeypatch.setattr("urllib3.PoolManager.request", mock_request_404)
    result = url_json("http://example.com/")
    assert not result.success
    assert "404" in result.log
    assert "error" in result.log
    assert "message" in result.log


def test_system_load():
    result = system_load(max_load_fraction=100.0)
    assert result.success
    assert "System load" in result.log


def test_lsof_count(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout="123\n456\n"
        ),
    )
    result = lsof_count()
    assert result.success
    assert "Number of open files" in result.log


def test_count_processes():
    result = count_processes()
    assert result.success
    assert "Number of processes" in result.log


def test_ps_count_with_threads(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout="thread1\nthread2\n"
        ),
    )
    result = ps_count_with_threads()
    assert result.success
    assert "Number of open processes&threads" in result.log


def test_disk_usage_low(monkeypatch):
    def mock_disk_usage(_):
        return type("Mock", (), {"percent": 50, "total": 90})

    monkeypatch.setattr(psutil, "disk_usage", mock_disk_usage)
    result = disk_usage("/mock")
    assert result.success is True
    assert "The usage of /mock is 50%, while the threshold is 85%" in result.log


def test_disk_usage_high(monkeypatch):
    def mock_disk_usage(_):
        return type("Mock", (), {"percent": 90, "total": 90})

    monkeypatch.setattr(psutil, "disk_usage", mock_disk_usage)
    result = disk_usage("/mock")
    assert result.success is False
    assert "The usage of /mock is 90%, while the threshold is 85%" in result.log


def test_memory_usage():
    result = memory_usage()
    assert result.success
    assert "Total memory" in result.log
    assert "Free memory" in result.log
    assert "Percent" in result.log


def test_check_mounts(tmp_path):
    with open(f"{tmp_path}/test", "w") as f:
        f.write("test")
    out = check_mounts(mounts=[tmp_path.as_posix()])
    assert out.success
    assert "1" in out.log

    out = check_mounts(mounts="/invalid/path")
    assert not out.success


def test_service_logs():
    out = service_logs(
        service="dbus.service",
        time_interval="4 hours ago",
        target_words=["dbus", "daemon"],
    )
    assert "dbus-daemon" in out.log


def test_service_is_active_success(mock_subprocess_run):
    result = service_is_active(["my-service"])
    assert result.log == json.dumps({"my-service": "active"}, indent=2)
    assert result.success is True


def test_service_is_active_inactive(mock_subprocess_run):
    result = service_is_active(["inactive-service"])
    assert result.log == json.dumps({"inactive-service": "inactive"}, indent=2)
    assert result.success is False


def test_service_is_active_failure(mock_subprocess_run):
    result = service_is_active(["fail"])
    assert result.success is False


def test_service_multiple(mock_subprocess_run):
    result = service_is_active(["service_1", "service_2"])
    assert result.log == json.dumps(
        {"service_1": "active", "service_2": "inactive"}, indent=2
    )
    assert result.success is False
