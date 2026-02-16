from pathlib import Path
from fractal_healthcheck.report import load_general_config


def test_load_general_config():
    basedir = Path(__file__).parent

    config = load_general_config(basedir / "config_without_general_key.yaml")
    assert config.max_log_size == 20_000

    config = load_general_config(basedir / "config_with_general_key.yaml")
    assert config.max_log_size == 20_000

    config = load_general_config(basedir / "config_with_general_key_and_value.yaml")
    assert config.max_log_size == 100
