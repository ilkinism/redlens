import json

from redlens.config import Config, load_config


def test_defaults_when_no_file(tmp_path):
    config = load_config(tmp_path / "absent.json")
    assert config == Config()


def test_file_values_are_read(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"port": 3999, "max_changes": 12}))
    config = load_config(path)
    assert config.port == 3999
    assert config.max_changes == 12


def test_the_environment_wins_over_the_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"port": 3999}))
    monkeypatch.setenv("REDLENS_PORT", "4100")
    assert load_config(path).port == 4100


def test_a_nonsense_value_falls_back_rather_than_crashing(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"port": "not a port", "host": "0.0.0.0"}))
    config = load_config(path)
    assert config.port == Config().port
    assert config.host == "0.0.0.0"


def test_a_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ this is not json")
    assert load_config(path) == Config()
