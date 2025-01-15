import json
import subprocess
from fractal_healthcheck.checks.implementations import (
    subprocess_run,
    check_mounts,
    system_load,
    url_json,
    lsof_count,
    count_processes,
    ps_count_with_threads,
    df,
    memory_usage,
)


def test_subprocess_run():
    result = subprocess_run("echo 'Hello, World!'")
    assert result.success
    assert "Hello, World!" in result.log


def test_url_json(monkeypatch):
    def mock_urlopen(url):
        class MockResponse:
            def read(self):
                return json.dumps({"test": "value"}).encode()

        return MockResponse()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    result = url_json("http://example.com")
    assert result.success
    assert "test" in result.log
    assert "value" in result.log


def test_system_load():
    result = system_load(max_load=100.0)
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


def test_df(tmp_path):
    with open(tmp_path / "testfile", "w") as f:
        f.write("test")
    result = df(mountpoint=tmp_path.as_posix())
    assert result.success
    assert "Filesystem" in result.log or "Size" in result.log


def test_memory_usage():
    result = memory_usage()
    assert result.success
    assert "total" in result.log
    assert "available" in result.log


def test_check_mounts(tmp_path):
    with open(f"{tmp_path}/test", "w") as f:
        f.write("test")
    out = check_mounts(mounts=[tmp_path.as_posix()])
    assert out.success
    assert "1" in out.log
