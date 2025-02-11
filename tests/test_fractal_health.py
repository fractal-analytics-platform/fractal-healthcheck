from fractal_healthcheck.main import main
import requests
import shutil
from click.testing import CliRunner
from pathlib import Path

testspath = Path(__file__).parent


def _modify_yaml_config_file(old_config_file: Path, tmp_path: Path) -> Path:
    """
    Make a temporary copy of the YAML config file and change its 'status_file'
    """
    config_file = tmp_path / "config.yaml"
    shutil.copy(old_config_file, config_file)
    with config_file.open("r") as f:
        old_yaml_content = f.read()
    new_yaml_content = old_yaml_content.replace(
        'status_file: "./status.yaml"',
        f'status_file: "{tmp_path.as_posix()}/status-success.yaml"',
    )
    with config_file.open("w") as f:
        f.write(new_yaml_content)
    print(f"{config_file.as_posix()=}")
    return config_file


def _current_num_messages() -> int:
    res = requests.get("http://localhost:8025/api/v1/messages")
    return res.json()["total"]


def test_successful_run(tmp_path: Path, caplog):
    caplog.set_level(0)
    initial_num_messages = _current_num_messages()

    old_config_file = testspath / "checks_config_success.yaml"
    config_file = _modify_yaml_config_file(
        old_config_file=old_config_file, tmp_path=tmp_path
    )

    runner = CliRunner(mix_stderr=False)
    report_file = tmp_path / "report.txt"
    args = f"{config_file.as_posix()} -o {report_file.as_posix()} -s -l DEBUG"

    caplog.clear()
    result = runner.invoke(main, args=args)
    assert result.exit_code == 0
    assert "Cannot read status_file" in caplog.text
    assert "I will send an email" in caplog.text
    assert "First report" in caplog.text
    assert _current_num_messages() == initial_num_messages + 1

    with report_file.open("r") as f:
        report = f.read()
    assert "Total number of checks: 8" in report
    assert "Number of failed checks: 0" in report
    assert "Email sent" in caplog.text

    caplog.clear()
    result = runner.invoke(main, args=args)
    assert result.exit_code == 0
    assert "Last report email sent on" in caplog.text
    assert "Email sent" in caplog.text
    assert _current_num_messages() == initial_num_messages + 2


def test_failing_run(tmp_path: Path, caplog):
    caplog.set_level(0)
    initial_num_messages = _current_num_messages()

    old_config_file = testspath / "checks_config_fail.yaml"
    config_file = _modify_yaml_config_file(
        old_config_file=old_config_file, tmp_path=tmp_path
    )

    runner = CliRunner(mix_stderr=False)
    report_file = tmp_path / "report.txt"
    args = f"{config_file.as_posix()} -o {report_file.as_posix()} -s -l DEBUG"

    caplog.clear()
    result = runner.invoke(main, args=args)
    assert result.exit_code == 0
    assert "Cannot read status_file" in caplog.text
    assert "I will send an email" in caplog.text
    assert "First report" in caplog.text
    assert "Email sent" in caplog.text

    with report_file.open("r") as f:
        report = f.read()
    assert "Total number of checks: 1" in report
    assert "Number of failed checks: 1" in report
    assert "Email sent" in caplog.text
    assert _current_num_messages() == initial_num_messages + 1

    caplog.clear()
    result = runner.invoke(main, args=args)
    assert result.exit_code == 0
    assert "Last report email sent on" in caplog.text
    assert "Email sent" in caplog.text
    assert _current_num_messages() == initial_num_messages + 2
