"""Runtime configuration for Kothon."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SubtitleRules(BaseModel):
    max_chars_per_line: int = Field(default=42, ge=1)
    max_lines_per_card: int = Field(default=2, ge=1)
    min_duration_seconds: float = Field(default=1.0, gt=0)
    max_duration_seconds: float = Field(default=7.0, gt=0)
    max_reading_speed_cps: float = Field(default=17.0, gt=0)


class ProviderConfig(BaseModel):
    transcription: str = "fixture"
    segmentation: str = "fixture"
    correction: str = "fixture"
    tagging: str = "fixture"
    compliance: str = "fixture"


class RuntimeConfig(BaseModel):
    max_correction_attempts: int = Field(default=2, ge=0, le=5)
    request_timeout_seconds: float = Field(default=60.0, gt=0)
    keep_trace: bool = True


class OutputConfig(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["srt", "vtt", "json"])


class KothonConfig(BaseModel):
    language_hint: str = "bn"
    subtitle_rules: SubtitleRules = Field(default_factory=SubtitleRules)
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(path: Path) -> KothonConfig:
    """Load and validate a YAML configuration file."""
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return KothonConfig.model_validate(raw)

