from __future__ import annotations

from pathlib import Path

from perturb_lm.config import PerturbLMConfig


def test_config_defaults(monkeypatch) -> None:
    for key in [
        "PERTURB_LM_DATA_ROOT",
        "PERTURB_LM_RAW_DIR",
        "PERTURB_LM_PROCESSED_DIR",
        "PERTURB_LM_OUTPUT_DIR",
        "PERTURB_LM_MODEL_DIR",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = PerturbLMConfig()

    assert config.raw_dir == Path("data/raw")
    assert config.processed_dir == Path("data/processed")
    assert config.output_dir == Path("outputs")
    assert config.model_dir == Path("models")


def test_config_env_and_ensure_dirs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PERTURB_LM_DATA_ROOT", str(tmp_path / "dataset"))
    monkeypatch.setenv("PERTURB_LM_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("PERTURB_LM_MODEL_DIR", str(tmp_path / "models"))

    config = PerturbLMConfig()
    config.ensure_dirs()

    assert config.raw_dir == tmp_path / "dataset" / "raw"
    assert config.processed_dir == tmp_path / "dataset" / "processed"
    assert config.raw_dir.exists()
    assert config.processed_dir.exists()
    assert config.output_dir.exists()
    assert config.model_dir.exists()
