from __future__ import annotations

import json

from perturb_lm.engineering.runtime import (
    PipelineRuntimeLogger,
    RuntimeLogger,
    dashboard_safe_runtime_summary,
    write_runtime_log,
)


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


def test_pipeline_runtime_logger_records_successful_and_nested_stages() -> None:
    logger = PipelineRuntimeLogger(
        dataset_track="jump_cpjump1_profiles",
        seed=3,
        split_name="held_out_plate",
    )
    with logger.stage("data_loading"):
        with logger.stage("schema_validation"):
            pass
    payload = logger.finish()
    safe = dashboard_safe_runtime_summary(payload)

    assert payload["schema_version"] == "1.1"
    assert payload["stage_count"] == 2
    assert {stage["status"] for stage in payload["stages"]} == {"success"}
    assert safe["stage_count"] == 2
    assert safe["stages"][0]["stage_name"] == "schema_validation"
    assert "memory_available" in safe


def test_pipeline_runtime_logger_records_failed_stage() -> None:
    logger = PipelineRuntimeLogger(dataset_track="synthetic", seed=0)

    try:
        with logger.stage("preprocessing_fit"):
            raise RuntimeError("synthetic failure")
    except RuntimeError:
        pass

    payload = logger.finish()
    stage = payload["stages"][0]
    assert stage["status"] == "failure"
    assert stage["error_type"] == "RuntimeError"
    assert stage["error_message"] == "synthetic failure"


def test_dashboard_safe_runtime_summary_excludes_paths_fields_and_identifiers() -> None:
    payload = {
        "schema_version": "1.1",
        "dataset_track": "jump_cpjump1_profiles",
        "seed": 0,
        "split_name": "held_out_plate",
        "elapsed_seconds": 1.0,
        "stage_count": 1,
        "memory": {"memory_available": False},
        "warnings": ["unsafe /Users/example/data.csv Metadata_Plate BRD-A profile-1"],
        "stages": [
            {
                "stage_name": "retrieval",
                "status": "success",
                "elapsed_seconds": 0.5,
                "seed": 0,
                "split_name": "held_out_plate",
                "dataset_track": "jump_cpjump1_profiles",
                "memory_end": {"memory_available": False},
                "warnings": ["unsafe"],
            }
        ],
    }

    text = json.dumps(dashboard_safe_runtime_summary(payload))

    assert "/Users/" not in text
    assert "Metadata_" not in text
    assert "BRD-" not in text
    assert "profile-1" not in text
    assert "data.csv" not in text
    assert '"warning_count": 1' in text
