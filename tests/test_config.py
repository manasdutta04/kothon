from pathlib import Path

from kothon.config import load_config


def test_default_config_loads() -> None:
    config = load_config(Path("config/default.yaml"))

    assert config.language_hint == "bn"
    assert config.subtitle_rules.max_chars_per_line == 42
    assert config.providers.transcription == "fixture"

