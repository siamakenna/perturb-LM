"""Runtime and memory logging helpers."""

from __future__ import annotations

import json
import platform
import sys
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
PIPELINE_SCHEMA_VERSION = "1.1"


@dataclass
class RuntimeLogger:
    """Best-effort runtime logger that never requires platform-specific packages."""

    start_time_utc: str
    start_monotonic: float
    tracemalloc_started_by_logger: bool = False
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def start(cls) -> RuntimeLogger:
        warnings: list[str] = []
        tracemalloc_started_by_logger = False
        try:
            if not tracemalloc.is_tracing():
                tracemalloc.start()
                tracemalloc_started_by_logger = True
        except Exception as exc:  # pragma: no cover - defensive platform guard
            warnings.append(f"Could not start tracemalloc memory measurement: {exc}")
        return cls(
            start_time_utc=_utc_now(),
            start_monotonic=time.perf_counter(),
            tracemalloc_started_by_logger=tracemalloc_started_by_logger,
            warnings=warnings,
        )

    def finish(
        self,
        *,
        extra: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a JSON-serializable runtime log payload."""

        end_time_utc = _utc_now()
        memory_warnings = list(self.warnings)
        memory_current_bytes: int | None = None
        memory_peak_bytes: int | None = None
        memory_source: str | None = None
        try:
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                memory_current_bytes = int(current)
                memory_peak_bytes = int(peak)
                memory_source = "tracemalloc_python_allocations"
        except Exception as exc:  # pragma: no cover - defensive platform guard
            memory_warnings.append(f"Could not read tracemalloc memory measurement: {exc}")

        process_peak = _process_peak_memory_bytes(memory_warnings)
        if memory_current_bytes is None and memory_peak_bytes is None and process_peak is None:
            memory_warnings.append("Memory measurement is unavailable on this platform.")

        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "start_time_utc": self.start_time_utc,
            "end_time_utc": end_time_utc,
            "elapsed_seconds": round(time.perf_counter() - self.start_monotonic, 6),
            "python_version": sys.version,
            "platform": platform.platform(),
            "memory_current_bytes": memory_current_bytes,
            "memory_peak_bytes": memory_peak_bytes,
            "process_peak_memory_bytes": process_peak,
            "memory_source": memory_source,
            "warnings": [*(warnings or []), *memory_warnings],
        }
        if extra:
            payload.update(extra)
        return payload


def write_runtime_log(path: Path | str, payload: dict[str, Any]) -> Path:
    """Write a runtime log JSON file and return its path."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


@dataclass
class PipelineRuntimeLogger:
    """Structured stage-level runtime logger for end-to-end workflows."""

    dataset_track: str
    seed: int | None = None
    split_name: str | None = None
    start_time_utc: str = field(default_factory=lambda: _utc_now())
    start_monotonic: float = field(default_factory=time.perf_counter)
    stages: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @contextmanager
    def stage(
        self,
        name: str,
        *,
        seed: int | None = None,
        split_name: str | None = None,
        warnings: list[str] | None = None,
    ):
        """Record one pipeline stage with success/failure status."""

        record = _StageRecord.start(
            name=name,
            dataset_track=self.dataset_track,
            seed=self.seed if seed is None else seed,
            split_name=self.split_name if split_name is None else split_name,
        )
        try:
            yield record
        except Exception as exc:
            self.stages.append(record.finish(status="failure", exc=exc, warnings=warnings))
            raise
        else:
            self.stages.append(record.finish(status="success", warnings=warnings))

    def finish(self, *, warnings: list[str] | None = None) -> dict[str, Any]:
        """Return a JSON-serializable pipeline runtime payload."""

        memory = _memory_snapshot()
        payload_warnings = [*self.warnings, *(warnings or [])]
        if memory["memory_available"] is False:
            payload_warnings.append("Memory measurement is unavailable on this platform.")
        return {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "dataset_track": self.dataset_track,
            "seed": self.seed,
            "split_name": self.split_name,
            "start_time_utc": self.start_time_utc,
            "end_time_utc": _utc_now(),
            "elapsed_seconds": round(time.perf_counter() - self.start_monotonic, 6),
            "stage_count": len(self.stages),
            "stages": self.stages,
            "memory": memory,
            "warnings": payload_warnings,
        }


@dataclass
class _StageRecord:
    name: str
    dataset_track: str
    seed: int | None
    split_name: str | None
    start_time_utc: str
    start_monotonic: float
    start_memory: dict[str, Any]

    @classmethod
    def start(
        cls,
        *,
        name: str,
        dataset_track: str,
        seed: int | None,
        split_name: str | None,
    ) -> _StageRecord:
        return cls(
            name=name,
            dataset_track=dataset_track,
            seed=seed,
            split_name=split_name,
            start_time_utc=_utc_now(),
            start_monotonic=time.perf_counter(),
            start_memory=_memory_snapshot(),
        )

    def finish(
        self,
        *,
        status: str,
        exc: BaseException | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        end_memory = _memory_snapshot()
        payload = {
            "stage_name": self.name,
            "dataset_track": self.dataset_track,
            "seed": self.seed,
            "split_name": self.split_name,
            "start_time_utc": self.start_time_utc,
            "end_time_utc": _utc_now(),
            "elapsed_seconds": round(time.perf_counter() - self.start_monotonic, 6),
            "status": status,
            "memory_start": self.start_memory,
            "memory_end": end_memory,
            "warnings": warnings or [],
        }
        if exc is not None:
            payload["error_type"] = type(exc).__name__
            payload["error_message"] = str(exc)
        return payload


def dashboard_safe_runtime_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a public-safe aggregate runtime summary."""

    safe_stages = []
    for stage in payload.get("stages", []):
        safe_stages.append(
            {
                "stage_name": stage.get("stage_name", ""),
                "status": stage.get("status", ""),
                "elapsed_seconds": stage.get("elapsed_seconds", 0),
                "seed": stage.get("seed"),
                "split_name": stage.get("split_name"),
                "dataset_track": stage.get("dataset_track"),
                "memory_available": stage.get("memory_end", {}).get("memory_available"),
                "warning_count": len(stage.get("warnings", [])),
            }
        )
    return {
        "schema_version": payload.get("schema_version", PIPELINE_SCHEMA_VERSION),
        "dataset_track": payload.get("dataset_track"),
        "seed": payload.get("seed"),
        "split_name": payload.get("split_name"),
        "elapsed_seconds": payload.get("elapsed_seconds", 0),
        "stage_count": payload.get("stage_count", len(safe_stages)),
        "stages": safe_stages,
        "memory_available": payload.get("memory", {}).get("memory_available"),
        "warning_count": len(payload.get("warnings", [])),
    }


def _memory_snapshot() -> dict[str, Any]:
    warnings: list[str] = []
    current: int | None = None
    peak: int | None = None
    source: str | None = None
    try:
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            source = "tracemalloc_python_allocations"
    except Exception:
        current = None
        peak = None
    process_peak = _process_peak_memory_bytes(warnings)
    return {
        "memory_available": any(value is not None for value in [current, peak, process_peak]),
        "memory_current_bytes": int(current) if current is not None else None,
        "memory_peak_bytes": int(peak) if peak is not None else None,
        "process_peak_memory_bytes": process_peak,
        "memory_source": source,
    }


def _process_peak_memory_bytes(warnings: list[str]) -> int | None:
    try:
        import resource  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
    except Exception as exc:  # pragma: no cover - defensive platform guard
        warnings.append(f"Could not read process peak memory measurement: {exc}")
        return None
    value = int(usage.ru_maxrss)
    if value <= 0:
        return None
    if sys.platform == "darwin":
        return value
    return value * 1024


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
