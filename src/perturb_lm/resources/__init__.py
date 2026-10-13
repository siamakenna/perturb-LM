"""Bundled policy snapshots, byte-checked against the reviewed repository contracts."""

from importlib.resources import files

import yaml


def policy_document(name):
    if name not in {"model_assets", "relevance_contracts"}:
        raise ValueError("Unknown bundled policy resource")
    return yaml.safe_load(files(__package__).joinpath(f"{name}.yaml").read_text(encoding="utf-8"))
