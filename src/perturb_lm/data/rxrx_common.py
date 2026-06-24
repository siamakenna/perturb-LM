"""Shared RxRx downloader and manifest helpers."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from perturb_lm.schemas import SITE_MANIFEST_COLUMNS, validate_site_manifest

LOGGER = logging.getLogger(__name__)

SUPPORTED_RXRX_DATASETS = {"rxrx1", "rxrx19a"}
SUPPORTED_DOWNLOADS = {"metadata", "embeddings", "images"}
METADATA_EXTENSIONS = {".csv", ".tsv", ".parquet"}

# TODO: Replace placeholders with verified public RxRx metadata and embedding URLs.
RXRX_URLS: dict[str, dict[str, str]] = {
    "rxrx1": {
        "metadata": "TODO_PUBLIC_URL_FOR_RXRX1_METADATA",
        "embeddings": "TODO_PUBLIC_URL_FOR_RXRX1_EMBEDDINGS",
        "images": "TODO_PUBLIC_URL_FOR_RXRX1_IMAGES",
    },
    "rxrx19a": {
        "metadata": "TODO_PUBLIC_URL_FOR_RXRX19A_METADATA",
        "embeddings": "TODO_PUBLIC_URL_FOR_RXRX19A_EMBEDDINGS",
        "images": "TODO_PUBLIC_URL_FOR_RXRX19A_IMAGES",
    },
}


@dataclass(frozen=True)
class DownloadPlan:
    dataset: str
    resource: str
    url: str
    out_path: Path


@dataclass(frozen=True)
class SiteManifestStandardizationReport:
    dataset: str
    source_metadata_file: str | None
    n_raw_rows: int
    raw_columns: list[str]
    column_mappings: dict[str, str | None]
    optional_fields_missing: list[str]
    required_fields_missing: list[str]
    defaults_applied: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_dataset(dataset: str) -> str:
    normalized = dataset.lower().strip()
    if normalized not in SUPPORTED_RXRX_DATASETS:
        raise ValueError(f"Unsupported dataset '{dataset}'. Expected one of: {sorted(SUPPORTED_RXRX_DATASETS)}")
    return normalized


def parse_download_values(values: list[str]) -> list[str]:
    downloads: list[str] = []
    for value in values:
        downloads.extend(part.strip().lower() for part in value.split(",") if part.strip())
    invalid = sorted(set(downloads) - SUPPORTED_DOWNLOADS)
    if invalid:
        raise ValueError(f"Unsupported download value(s): {invalid}. Expected: {sorted(SUPPORTED_DOWNLOADS)}")
    return list(dict.fromkeys(downloads))


def build_download_plan(dataset: str, downloads: list[str], out_dir: Path) -> list[DownloadPlan]:
    dataset = normalize_dataset(dataset)
    plans = []
    for resource in downloads:
        url = RXRX_URLS[dataset][resource]
        suffix = ".zip" if resource == "images" else ".tar.gz"
        plans.append(DownloadPlan(dataset, resource, url, out_dir / dataset / f"{resource}{suffix}"))
    return plans


def download_plans(
    plans: list[DownloadPlan],
    *,
    dry_run: bool,
    confirm_large_download: bool,
) -> None:
    for plan in plans:
        if plan.resource == "images" and not confirm_large_download:
            raise ValueError(
                "Image downloads are large and opt-in only. Re-run with --confirm-large-download "
                "if you intentionally want full images."
            )
        if dry_run:
            print(f"DRY RUN: would download {plan.dataset} {plan.resource} from {plan.url} to {plan.out_path}")
            continue
        if plan.url.startswith("TODO_"):
            raise ValueError(
                f"No verified public URL is configured for {plan.dataset} {plan.resource}. "
                "Update RXRX_URLS in perturb_lm.data.rxrx_common first."
            )
        _stream_download(plan.url, plan.out_path)


def _stream_download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        with out_path.open("wb") as handle, tqdm(
            total=total or None,
            unit="B",
            unit_scale=True,
            desc=out_path.name,
        ) as progress:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    progress.update(len(chunk))


def make_perturbation_key(
    dataset: str,
    perturbation_id: object,
    perturbation_name: object,
    cell_type: object,
    condition_label: object,
    concentration: object,
) -> str:
    parts = [dataset, perturbation_id, perturbation_name, cell_type, condition_label, concentration]
    return "::".join(str(part).strip().replace(" ", "_") or "NA" for part in parts)


def find_metadata_files(dataset: str, data_root: Path) -> list[Path]:
    """Find likely metadata tables under a local RxRx data root."""

    dataset = normalize_dataset(dataset)
    data_root = Path(data_root)
    if not data_root.exists():
        raise FileNotFoundError(f"Data root does not exist: {data_root}")

    priority_names = [
        f"{dataset}_site_metadata.csv",
        f"{dataset}_metadata.csv",
        "site_metadata.csv",
        "metadata.csv",
        "metadata.tsv",
        "metadata.parquet",
    ]
    search_roots = [data_root / dataset, data_root]
    found: list[Path] = []
    for root in search_roots:
        for name in priority_names:
            candidate = root / name
            if candidate.exists() and candidate not in found:
                found.append(candidate)
    if found:
        return found

    keywords = ("metadata", "site", "experiment", "well", "plate", "sirna", "compound")
    for path in sorted(data_root.rglob("*")):
        if path.suffix.lower() in METADATA_EXTENSIONS and any(key in path.name.lower() for key in keywords):
            found.append(path)
    return found


def read_metadata_table(path: Path) -> pd.DataFrame:
    """Read a supported local metadata table."""

    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".tsv":
        return pd.read_csv(path, sep="\t")
    return pd.read_csv(path)


def load_rxrx_metadata(dataset: str, data_root: Path) -> pd.DataFrame:
    """Load the first parseable RxRx metadata table from a local data root."""

    files = find_metadata_files(dataset, data_root)
    if not files:
        raise FileNotFoundError(
            f"No metadata files found for {dataset} under {data_root}. "
            "Expected CSV/TSV/parquet metadata; raw image archives are not required."
        )
    failures: list[str] = []
    for path in files:
        try:
            frame = read_metadata_table(path)
        except Exception as exc:  # pragma: no cover - defensive for varied real files
            failures.append(f"{path}: {exc}")
            continue
        if frame.empty:
            failures.append(f"{path}: table is empty")
            continue
        LOGGER.info("Loaded %s metadata rows from %s", len(frame), path)
        return frame
    raise ValueError("Unable to load any candidate metadata file. " + " | ".join(failures))


def standardize_site_manifest(dataset: str, raw: pd.DataFrame) -> pd.DataFrame:
    """Best-effort conversion of fixture or RxRx-like metadata to the site manifest schema."""

    site_manifest, _ = standardize_site_manifest_with_report(dataset, raw)
    return site_manifest


def standardize_site_manifest_with_report(
    dataset: str,
    raw: pd.DataFrame,
    *,
    source_metadata_file: Path | str | None = None,
) -> tuple[pd.DataFrame, SiteManifestStandardizationReport]:
    """Convert fixture or RxRx-like metadata to the site manifest schema with provenance."""

    dataset = normalize_dataset(dataset)
    raw_columns = [str(column) for column in raw.columns]
    raw, normalized_to_original = _normalize_column_names(raw)
    aliases = {
        "experiment": [
            "experiment",
            "metadata_experiment",
            "batch",
            "batch_id",
            "metadata_batch",
            "experiment_id",
            "experiment_name",
            "imaging_batch",
        ],
        "plate": ["plate", "metadata_plate", "plate_id", "plate_name", "metadata_plate_id"],
        "well": ["well", "metadata_well", "well_id", "well_name", "metadata_well_id"],
        "site": ["site", "metadata_site", "field", "field_id", "field_of_view", "fov"],
        "cell_type": [
            "cell_type",
            "metadata_cell_type",
            "metadata_celltype",
            "cell_line",
            "metadata_cell_line",
            "celltype",
            "cell",
            "cells",
        ],
        "perturbation_id": [
            "perturbation_id",
            "sirna_id",
            "sirna",
            "gene_id",
            "compound_id",
            "compound",
            "metadata_broad_sample",
            "metadata_pert_id",
            "metadata_perturbation_id",
            "treatment_id",
            "sample_id",
            "metadata_treatment_id",
        ],
        "perturbation_name": [
            "perturbation_name",
            "sirna_name",
            "gene",
            "gene_symbol",
            "target",
            "compound_name",
            "compound",
            "metadata_pert_iname",
            "metadata_perturbation_name",
            "treatment",
            "treatment_name",
            "metadata_treatment",
        ],
        "perturbation_type": [
            "perturbation_type",
            "pert_type",
            "metadata_pert_type",
            "treatment_type",
            "well_type",
            "metadata_well_type",
        ],
        "condition_label": [
            "condition_label",
            "infection_condition",
            "metadata_condition",
            "disease_condition",
            "viral_condition",
            "infection_status",
            "treatment_condition",
            "well_type",
            "phenotype",
            "mock",
            "infected",
            "is_infected",
            "sars_cov_2",
        ],
        "concentration": [
            "concentration",
            "dose",
            "metadata_dose",
            "compound_concentration",
            "treatment_conc",
            "treatment_concentration",
            "metadata_treatment_conc",
            "metadata_dose_value",
        ],
        "split": ["split", "metadata_split"],
    }
    column_mappings: dict[str, str | None] = {}
    out = pd.DataFrame(index=raw.index)
    out["dataset"] = dataset
    for column, candidates in aliases.items():
        out[column], source = _first_available_with_source(raw, candidates, default="")
        column_mappings[column] = _original_name(source, normalized_to_original)

    if dataset == "rxrx1":
        out["cell_type"] = out["cell_type"].replace("", "HUVEC")
        out["perturbation_type"] = out["perturbation_type"].replace("", "siRNA")
        out["condition_label"] = out["condition_label"].replace("", "siRNA perturbation")
    if dataset == "rxrx19a":
        out["condition_label"] = _rxrx19a_condition(raw, out["condition_label"])
        out["perturbation_type"] = out["perturbation_type"].replace("", "compound")

    optional_fields = ["cell_type", "condition_label", "perturbation_name", "concentration"]
    optional_missing = [column for column in optional_fields if column_mappings.get(column) is None]
    defaults_applied = _defaults_applied(dataset, optional_missing)
    _warn_optional_missing(dataset, out)
    required_missing = _missing_required(out, ["experiment", "plate", "well", "perturbation_id"])
    if required_missing:
        report = SiteManifestStandardizationReport(
            dataset=dataset,
            source_metadata_file=str(source_metadata_file) if source_metadata_file else None,
            n_raw_rows=len(raw),
            raw_columns=raw_columns,
            column_mappings=column_mappings,
            optional_fields_missing=optional_missing,
            required_fields_missing=required_missing,
            defaults_applied=defaults_applied,
        )
        raise ValueError(
            f"{dataset} metadata is missing required fields that cannot be inferred: "
            f"{', '.join(required_missing)}. Standardization report: {report.to_dict()}"
        )

    for channel in range(1, 7):
        out[f"image_path_ch{channel}"], source = _first_available_with_source(
            raw,
            [
                f"image_path_ch{channel}",
                f"channel_{channel}",
                f"path_ch{channel}",
                f"metadata_channel_{channel}",
                f"metadata_image_path_ch{channel}",
                f"image_path_w{channel}",
                f"path_w{channel}",
            ],
            default="",
        )
        column_mappings[f"image_path_ch{channel}"] = _original_name(source, normalized_to_original)
        missing_image_path = out[f"image_path_ch{channel}"].astype(str).str.strip() == ""
        out.loc[missing_image_path, f"image_path_ch{channel}"] = _logical_image_paths(out, channel)

    out["site"] = out["site"].replace("", "1")
    out["split"] = out["split"].replace("", "train")
    out["site_id"], source = _first_available_with_source(raw, ["site_id", "metadata_site_id"], default="")
    column_mappings["site_id"] = _original_name(source, normalized_to_original)
    missing_site_id = out["site_id"].astype(str).str.strip() == ""
    out.loc[missing_site_id, "site_id"] = (
        out.loc[missing_site_id, ["dataset", "experiment", "plate", "well", "site"]]
        .astype(str)
        .agg("::".join, axis=1)
    )
    out = out[SITE_MANIFEST_COLUMNS]
    validate_site_manifest(out)
    report = SiteManifestStandardizationReport(
        dataset=dataset,
        source_metadata_file=str(source_metadata_file) if source_metadata_file else None,
        n_raw_rows=len(raw),
        raw_columns=raw_columns,
        column_mappings=column_mappings,
        optional_fields_missing=optional_missing,
        required_fields_missing=[],
        defaults_applied=defaults_applied,
    )
    return out, report


def _normalize_column_names(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    normalized_columns = [_normalize_column_name(column) for column in raw.columns]
    normalized_to_original = {
        normalized: str(original)
        for normalized, original in zip(normalized_columns, raw.columns, strict=False)
        if normalized
    }
    renamed = raw.copy()
    renamed.columns = normalized_columns
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    return renamed, normalized_to_original


def _normalize_column_name(column: object) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", str(column).strip())).strip("_").lower()


def _first_available(raw: pd.DataFrame, candidates: list[str], default: str) -> pd.Series:
    series, _ = _first_available_with_source(raw, candidates, default)
    return series


def _first_available_with_source(
    raw: pd.DataFrame,
    candidates: list[str],
    default: str,
) -> tuple[pd.Series, str | None]:
    for candidate in candidates:
        if candidate in raw.columns:
            return raw[candidate].fillna("").astype(str), candidate
    return pd.Series([default] * len(raw), index=raw.index, dtype="object"), None


def _original_name(normalized: str | None, normalized_to_original: dict[str, str]) -> str | None:
    if normalized is None:
        return None
    return normalized_to_original.get(normalized, normalized)


def _logical_image_paths(out: pd.DataFrame, channel: int) -> pd.Series:
    return (
        out[["dataset", "experiment", "plate", "well", "site"]]
        .fillna("")
        .astype(str)
        .agg(lambda row: f"{row['dataset']}/{row['experiment']}/Plate{row['plate']}/{row['well']}_s{row['site']}_w{channel}.png", axis=1)
    )


def _warn_optional_missing(dataset: str, out: pd.DataFrame) -> None:
    optional = ["cell_type", "condition_label", "perturbation_name", "concentration"]
    for column in optional:
        if (out[column].astype(str).str.strip() == "").all():
            LOGGER.warning("%s metadata did not provide optional field '%s'; using blanks/defaults.", dataset, column)


def _require_inferable(out: pd.DataFrame, columns: list[str], dataset: str) -> None:
    missing = _missing_required(out, columns)
    if missing:
        raise ValueError(
            f"{dataset} metadata is missing required fields that cannot be inferred: {', '.join(missing)}."
        )


def _missing_required(out: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if (out[column].astype(str).str.strip() == "").all()]


def _defaults_applied(dataset: str, optional_missing: list[str]) -> dict[str, str]:
    defaults: dict[str, str] = {}
    if dataset == "rxrx1":
        if "cell_type" in optional_missing:
            defaults["cell_type"] = "HUVEC"
        if "condition_label" in optional_missing:
            defaults["condition_label"] = "siRNA perturbation"
        defaults["perturbation_type"] = "siRNA when missing"
    if dataset == "rxrx19a":
        if "condition_label" in optional_missing:
            defaults["condition_label"] = "viral condition"
        defaults["perturbation_type"] = "compound when missing"
    defaults["site"] = "1 when missing"
    defaults["split"] = "train when missing"
    defaults["image_path_ch1-6"] = "logical path strings when missing"
    defaults["site_id"] = "dataset::experiment::plate::well::site when missing"
    return defaults


def _rxrx19a_condition(raw: pd.DataFrame, fallback: pd.Series) -> pd.Series:
    for column in ["condition_label", "infection_condition", "viral_condition", "disease_condition"]:
        if column in raw.columns:
            return raw[column].fillna("").astype(str)
    for column in ["infected", "is_infected", "sars_cov_2", "mock"]:
        if column in raw.columns:
            values = raw[column].fillna("").astype(str).str.lower()
            return values.map(
                lambda value: "mock infected"
                if value in {"0", "false", "mock", "no"}
                else "SARS-CoV-2 infected"
                if value in {"1", "true", "infected", "yes", "sars-cov-2", "sars_cov_2"}
                else value
            )
    return fallback.replace("", "viral condition")
