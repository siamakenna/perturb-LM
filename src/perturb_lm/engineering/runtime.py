"""Runtime and memory logging helpers."""

from __future__ import annotations

import json
import platform
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"


@dataclass
class RuntimeLogger:
    """Best-effort runtime logger that never requires platform-specific packages."""

    start_time_utc: str
    start_monotonic: float
    tracemalloc_started_by_logger: bool = False
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def start(cls) -> "RuntimeLogger":
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
