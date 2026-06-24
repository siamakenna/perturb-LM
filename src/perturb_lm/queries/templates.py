"""Dataset-specific natural-language query templates."""

from __future__ import annotations

RXRX19A_TEMPLATES = [
    "SARS-CoV-2 infected {cell_type} cells treated with {perturbation_name}",
    "{condition_label} {cell_type} cells treated with {perturbation_name}",
    "viral condition cells treated with {perturbation_name}",
    "{cell_type} cells under {condition_label} condition treated with {perturbation_name} at {concentration}",
]

RXRX1_TEMPLATES = [
    "{cell_type} cells with siRNA perturbation {perturbation_id}",
    "{cell_type} cells with knockdown phenotype for {perturbation_name}",
    "cells treated with perturbation {perturbation_id}",
]

TEMPLATES_BY_DATASET = {
    "rxrx1": RXRX1_TEMPLATES,
    "rxrx19a": RXRX19A_TEMPLATES,
}


def templates_for_dataset(dataset: str) -> list[str]:
    try:
        return TEMPLATES_BY_DATASET[dataset.lower()]
    except KeyError as exc:
        raise ValueError(f"No query templates configured for dataset '{dataset}'.") from exc
