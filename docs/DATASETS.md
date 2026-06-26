# Datasets

The active real Cell Painting profile track is the JUMP CPJUMP1 pilot data under `data/raw/jump_pilot/`. This is the first Phase 2 local-data target because it supports a profile-based retrieval baseline before raw image or VLM work is required.

Local CPJUMP1 files are optional review/runtime inputs and should remain outside git. This PR covers Adam's Phase 2 profile-infrastructure and diagnostics path; raw microscopy images, VLM baselines, and text-query/RAG support remain later project layers.

RxRx1 and RxRx19a remain important future/generalization tracks unless real RxRx files are added locally. RxRx1 gives the benchmark a controlled perturbation setting where splits by experiment, plate, and batch can expose whether retrieval models are learning biology or shortcutting acquisition structure. RxRx19a remains the infectious-disease anchor for later SARS-CoV-2 perturbation retrieval questions.

JUMP Cell Painting `cpg0016-jump` is the large-scale Cell Painting expansion target. The current local pilot uses CPJUMP1 profile files from `2020_11_04_CPJUMP1` with profile kind `normalized_feature_select_negcon_batch`.

PERISCOPE / `cpg0021-periscope` is the optical pooled screening bridge. It is a later-stage target for connecting image-based retrieval to pooled-screen perturbation logic.

## Download Policy

Full image archives should not be downloaded by default. Metadata and embeddings are the first required downloads. Raw image handling should start with selective samples, thumbnails, or user-selected subsets before any full archive workflow is enabled.

The downloader requires an explicit `--confirm-large-download` flag before image downloads. Dry runs are supported and should be used to inspect planned actions.

## URL TODOs

The downloader currently centralizes RxRx URL placeholders in `src/perturb_lm/data/rxrx_common.py`. Replace those placeholders with verified public metadata and embedding URLs before using non-dry-run downloads. Do not add full image archive downloads without size notes, checksums when available, and the explicit confirmation guard.
