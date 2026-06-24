# Datasets

Perturb LM starts with RxRx19a as the infectious-disease anchor dataset. RxRx19a is the first target because it directly supports SARS-CoV-2 perturbation retrieval questions and keeps the initial benchmark aligned with the project mission.

RxRx1 is required alongside RxRx19a for batch and generalization stress testing. It gives the benchmark a controlled perturbation setting where splits by experiment, plate, and batch can expose whether retrieval models are learning biology or shortcutting acquisition structure.

JUMP Cell Painting `cpg0016-jump` is the large-scale Cell Painting expansion target. It is important for scale, perturbation diversity, and broader morphology retrieval, but it should not be the first large download dependency.

PERISCOPE / `cpg0021-periscope` is the optical pooled screening bridge. It is a later-stage target for connecting image-based retrieval to pooled-screen perturbation logic.

## Download Policy

Full image archives should not be downloaded by default. Metadata and embeddings are the first required downloads. Raw image handling should start with selective samples, thumbnails, or user-selected subsets before any full archive workflow is enabled.

The downloader requires an explicit `--confirm-large-download` flag before image downloads. Dry runs are supported and should be used to inspect planned actions.

## URL TODOs

The downloader currently centralizes RxRx URL placeholders in `src/perturb_lm/data/rxrx_common.py`. Replace those placeholders with verified public metadata and embedding URLs before using non-dry-run downloads. Do not add full image archive downloads without size notes, checksums when available, and the explicit confirmation guard.
