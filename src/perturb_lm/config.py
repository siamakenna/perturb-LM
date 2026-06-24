"""Configuration helpers for Perturb LM."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _path_from_env(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


@dataclass(frozen=True)
class PerturbLMConfig:
    """Filesystem configuration driven by environment variables."""

    data_root: Path = field(default_factory=lambda: _path_from_env("PERTURB_LM_DATA_ROOT", Path("data")))
    raw_dir: Path | None = None
    processed_dir: Path | None = None
    output_dir: Path = field(default_factory=lambda: _path_from_env("PERTURB_LM_OUTPUT_DIR", Path("outputs")))
    model_dir: Path = field(default_factory=lambda: _path_from_env("PERTURB_LM_MODEL_DIR", Path("models")))

    def __post_init__(self) -> None:
        raw_default = self.data_root / "raw"
        processed_default = self.data_root / "processed"
        object.__setattr__(
            self,
            "raw_dir",
            self.raw_dir or _path_from_env("PERTURB_LM_RAW_DIR", raw_default),
        )
        object.__setattr__(
            self,
            "processed_dir",
            self.processed_dir or _path_from_env("PERTURB_LM_PROCESSED_DIR", processed_default),
        )

    def ensure_dirs(self) -> None:
        """Create configured directories if they do not exist."""

        for path in [self.raw_dir, self.processed_dir, self.output_dir, self.model_dir]:
            Path(path).mkdir(parents=True, exist_ok=True)
