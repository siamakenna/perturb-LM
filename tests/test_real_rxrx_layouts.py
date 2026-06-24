from __future__ import annotations

import json

import pandas as pd

from scripts.build_rxrx_manifests import build_manifests


def test_rxrx1_real_style_metadata_layout_reports_column_mappings(tmp_path) -> None:
    data_root = tmp_path / "data"
    rxrx1 = data_root / "rxrx1"
    rxrx1.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "site_id": "HUVEC-1_1_A01_1",
                "experiment": "HUVEC-1",
                "plate": "1",
                "well": "A01",
                "site": "1",
                "cell_type": "HUVEC",
                "sirna_id": "1138",
                "gene": "ATP1A1",
                "well_type": "treatment",
            },
            {
                "site_id": "HUVEC-2_1_A01_1",
                "experiment": "HUVEC-2",
                "plate": "1",
                "well": "A01",
                "site": "1",
                "cell_type": "HUVEC",
                "sirna_id": "1138",
                "gene": "ATP1A1",
                "well_type": "treatment",
            },
        ]
    ).to_csv(rxrx1 / "metadata.csv", index=False)

    site, _, report = build_manifests("rxrx1", data_root, tmp_path / "processed", return_report=True)

    assert len(site) == 2
    assert report.source_metadata_file == str(rxrx1 / "metadata.csv")
    assert report.column_mappings["perturbation_id"] == "sirna_id"
    assert report.column_mappings["perturbation_name"] == "gene"
    assert "concentration" in report.optional_fields_missing
    report_path = tmp_path / "processed" / "rxrx1_manifest_build_report.json"
    assert json.loads(report_path.read_text())["source_metadata_file"] == str(rxrx1 / "metadata.csv")


def test_rxrx19a_metadata_layout_accepts_metadata_prefixed_columns(tmp_path) -> None:
    data_root = tmp_path / "data"
    rxrx19a = data_root / "rxrx19a"
    rxrx19a.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "Metadata_Experiment": "covid-1",
                "Metadata_Plate": "plate-1",
                "Metadata_Well": "B02",
                "Metadata_Site": "1",
                "cell_line": "HRCE",
                "treatment_id": "drug-1",
                "treatment": "Remdesivir",
                "treatment_type": "compound",
                "treatment_conc": "1 uM",
                "is_infected": True,
            },
            {
                "Metadata_Experiment": "covid-1",
                "Metadata_Plate": "plate-1",
                "Metadata_Well": "B03",
                "Metadata_Site": "1",
                "cell_line": "HRCE",
                "treatment_id": "vehicle",
                "treatment": "DMSO",
                "treatment_type": "control",
                "treatment_conc": "0 uM",
                "is_infected": False,
            },
        ]
    ).to_csv(rxrx19a / "site_metadata.csv", index=False)

    site, _, report = build_manifests("rxrx19a", data_root, tmp_path / "processed", return_report=True)

    assert site["condition_label"].tolist() == ["SARS-CoV-2 infected", "mock infected"]
    assert report.column_mappings["experiment"] == "Metadata_Experiment"
    assert report.column_mappings["concentration"] == "treatment_conc"
    assert report.optional_fields_missing == []
