# Week 1: JUMP Data and Baselines

## Submission Target If Successful

Best option: PSB 2027 full paper, if the benchmark/prototype has clean results by mid-July 2026.

Why PSB:

- The contribution is computational biology, not just ML.
- A perturbation/profile retrieval benchmark is a better fit for biological discovery and searchable datasets than for a pure computer-vision venue.
- Accepted PSB papers are archival proceedings papers and indexed.
- The current PSB paper deadline is 2026-08-03, so this is tight but viable if Week 1 yields signal.

Fallbacks:

- NeurIPS workshop submission if the result is more ML-method/prototype oriented; main NeurIPS 2026 deadlines have passed.
- Crick BioImage Analysis Symposium and Global BioImaging Exchange of Experience posters if the result is promising but not yet full-paper strong.
- PSB poster/abstract by 2026-12-01 if the full paper timeline is too compressed.

## Week 1 Objective

Produce the first quantitative perturbation/profile-level retrieval table on JUMP pilot profiles:

- Input: well-level CellProfiler morphology profiles.
- Query unit: metadata-derived text query or perturbation identity.
- Retrieval unit: aggregated perturbation profile.
- First baseline: image/profile-only cosine similarity.
- First metrics: Recall@K, mAP, and enrichment over random.

## Why Start With Profiles

Single-cell and field-level images are noisy, batch-sensitive, and expensive to encode. Perturbation/profile-level aggregation gives a more publishable benchmark because it asks whether the biological perturbation signal is recoverable after standard morphology-profile processing. The image-tile prototype can be layered on later for interpretability.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Download A Small JUMP Pilot Profile Subset

The script uses GitHub's `media.githubusercontent.com` endpoint because the CPJUMP1 profile files are stored via Git LFS.

```bash
python scripts/download_jump_pilot_profiles.py \
  --batch 2020_11_04_CPJUMP1 \
  --profile-kind normalized_feature_select_negcon_batch \
  --plate-limit 12
```

This writes:

- `data/raw/jump_pilot/profiles/...`
- `data/raw/jump_pilot/metadata/...`
- `data/interim/jump_pilot_profile_files.csv`

## Generate Metadata-Derived Queries

```bash
python scripts/generate_text_queries.py
```

This writes:

- `data/interim/jump_pilot_queries.csv`

The first query templates are deliberately simple and auditable:

- compound name queries,
- gene perturbation queries,
- target-aware compound queries when target metadata is available.

## Run Profile Retrieval Baseline

```bash
python scripts/run_profile_retrieval.py \
  --label-column Metadata_broad_sample \
  --top-k 1 5 10 25
```

This writes:

- `results/week1/profile_retrieval_summary.csv`
- `results/week1/profile_retrieval_per_perturbation.csv`
- `results/week1/profile_retrieval_top_hits.csv`
- `results/week1/well_replicate_retrieval_per_query.csv`
- `results/week1/well_replicate_retrieval_top_hits.csv`

For a gene-label sanity check:

```bash
python scripts/run_profile_retrieval.py \
  --label-column Metadata_gene \
  --top-k 1 5 10 25 \
  --out-dir results/week1_gene
```

## Initial Smoke-Test Results

Run date: 2026-06-23. Input: 12 CPJUMP1 profile plates from `2020_11_04_CPJUMP1`, `normalized_feature_select_negcon_batch`.

Broad sample labels:

- 641 aggregated perturbation profiles.
- 4,524 well-level profiles.
- Mean well-level AP: 0.1164.
- Mean hit@1 / hit@5 / hit@10 / hit@25: 0.1663 / 0.2821 / 0.3587 / 0.4857.
- Enrichment over random hit@1 / hit@5 / hit@10 / hit@25: 108.8x / 37.0x / 23.6x / 13.0x.

Gene labels:

- 160 aggregated gene profiles.
- 4,524 well-level profiles.
- Mean well-level AP: 0.0426.
- Mean hit@1 / hit@5 / hit@10 / hit@25: 0.1955 / 0.3340 / 0.4268 / 0.5830.
- Enrichment over random hit@1 / hit@5 / hit@10 / hit@25: 32.6x / 11.3x / 7.3x / 4.2x.

Interpretation: the exact perturbation replicate task shows usable signal immediately. The gene-label task is noisier but still retrieves same-gene wells in the top ranks often enough to justify a full Week 1 benchmark, especially with random baselines, control removal, and plate-held-out evaluation.

## Week 1 Success Criteria

Minimum:

- A reproducible profile manifest.
- 50 to 200 metadata-derived text queries.
- A profile-only cosine retrieval table.
- A qualitative list of top hits for representative perturbations.

Strong:

- Replicate/perturbation retrieval beats random by a wide margin.
- Results remain meaningful when controls are removed.
- Enough target/gene metadata is available to define a gene-compound or MoA-like retrieval task.

Next step after strong Week 1:

- Add text embeddings and a frozen projection baseline.
- Add held-out plate/batch splits.
- Add image thumbnails for prototype panels.
