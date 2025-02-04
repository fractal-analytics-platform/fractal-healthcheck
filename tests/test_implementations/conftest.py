import pytest
import paramiko
import subprocess


@pytest.fixture
def mock_ssh_client(monkeypatch):
    """Mock paramiko.SSHClient."""

    class MockSSHClient:
        def set_missing_host_key_policy(self, policy):
            pass

        def connect(self, host, username, pkey):
            if username == "fail":
                raise paramiko.AuthenticationException("Auth failed")

        def close(self):
            pass

    monkeypatch.setattr(paramiko, "SSHClient", MockSSHClient)
    return MockSSHClient()


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
