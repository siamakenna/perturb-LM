# Codex Tasks

- Keep core code under `src/perturb_lm/`.
- Keep scripts user-facing and ensure each supports `--help`.
- Do not download full raw image archives by default.
- Do not commit data, embeddings, images, models, parquet files, numpy arrays, or outputs.
- Add or update tiny synthetic tests for every user-facing behavior.
- Phase 1 retrieval must save both site-level and perturbation-level results.
- Formal scoring should use perturbation-level results after aggregation.
- Keep random, shuffled-label, and metadata lexical baselines runnable without internet.
- Be explicit that fixture/lexical baseline results are pipeline checks, not biological claims.
