import pytest
import subprocess


@pytest.fixture
def mock_subprocess_run(monkeypatch):
    """Mock subprocess.run to simulate systemctl responses."""

    def mock_run(cmd, capture_output, encoding):
        class MockCompletedProcess:
            def __init__(self, stdout):
                self.stdout = stdout

        # Simulate different service states
        if "fail" in cmd:
            raise subprocess.CalledProcessError(1, cmd, "error")
        elif "inactive-service" in cmd:
            return MockCompletedProcess("inactive")
        elif "service_1" in cmd and "service_2" in cmd:
            return MockCompletedProcess("active\ninactive\n")
        else:
            return MockCompletedProcess("active")

    monkeypatch.setattr(subprocess, "run", mock_run)
