import pytest
import paramiko


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
