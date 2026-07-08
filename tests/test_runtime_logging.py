from __future__ import annotations

import json

from perturb_lm.engineering.runtime import RuntimeLogger, write_runtime_log


def test_runtime_logger_records_times_platform_and_memory_fields(tmp_path) -> None:
    logger = RuntimeLogger.start()
    payload = logger.finish(
        extra={
            "artifact_type": "unit_test_runtime",
            "dataset": "synthetic",
            "row_count": 3,
            "feature_count": 2,
        }
    )
    runtime_path = write_runtime_log(tmp_path / "runtime_log.json", payload)
    saved = json.loads(runtime_path.read_text())

    assert saved["schema_version"] == "1.0"
    assert saved["artifact_type"] == "unit_test_runtime"
    assert saved["dataset"] == "synthetic"
    assert saved["row_count"] == 3
    assert saved["feature_count"] == 2
    assert saved["start_time_utc"].endswith("Z")
    assert saved["end_time_utc"].endswith("Z")
    assert saved["elapsed_seconds"] >= 0
    assert saved["python_version"]
    assert saved["platform"]
    assert "memory_current_bytes" in saved
    assert "memory_peak_bytes" in saved
    assert "process_peak_memory_bytes" in saved
    assert isinstance(saved["warnings"], list)
    if saved["memory_current_bytes"] is None and saved["memory_peak_bytes"] is None:
        assert any("Memory measurement is unavailable" in item for item in saved["warnings"])

