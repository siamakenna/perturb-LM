"""Minimal Streamlit prototype for Phase 1 retrieval inspection."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover - optional prototype dependency
    raise SystemExit(
        "Streamlit is optional. Install it with: python -m pip install streamlit"
    ) from exc

from perturb_lm.retrieval.search import run_retrieval


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


st.set_page_config(page_title="Perturb LM Prototype", layout="wide")
st.title("Perturb LM Phase 1 Prototype")

dataset = st.selectbox("Dataset", ["rxrx19a", "rxrx1"])
mode = st.selectbox("Retrieval mode", ["lexical", "random", "shuffled"])
query_text = st.text_input("Text query", value="SARS-CoV-2 infected cells treated with Remdesivir")
manifest_path = st.text_input("Site manifest path", value=f"data/processed/{dataset}_site_manifest.parquet")
top_k = st.slider("Top K", min_value=1, max_value=50, value=10)

if st.button("Run retrieval"):
    manifest = load_table(Path(manifest_path))
    query = pd.DataFrame(
        [
            {
                "query_id": "prototype_query",
                "dataset": dataset,
                "query_text": query_text,
                "query_type": "prototype",
                "positive_perturbation_keys": "",
                "positive_perturbation_ids": "",
                "condition_label": "",
                "cell_type": "",
                "split": "prototype",
            }
        ]
    )
    site_results, perturbation_results = run_retrieval(
        query,
        manifest,
        dataset=dataset,
        mode=mode,
        top_k=top_k,
        seed=0,
    )
    st.subheader("Top perturbation-level results")
    st.dataframe(perturbation_results)
    st.subheader("Site-level metadata")
    st.dataframe(site_results)

    image_columns = [column for column in manifest.columns if column.startswith("image_path_ch")]
    for image_column in image_columns[:1]:
        for path in manifest[image_column].head(5):
            local_path = Path(str(path))
            if local_path.exists():
                st.image(str(local_path), caption=str(local_path))
