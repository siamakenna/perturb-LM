# CI And Remote Smoke Tests

The repository now has a GitHub Actions workflow at `.github/workflows/ci.yml`.
The static project dashboard is deployed by `.github/workflows/pages.yml` from the `site/` directory.

## Automatic CI

On pull requests and pushes to `main`, CI runs:

```bash
python -m pytest
python scripts/run_phase1_smoke.py --out outputs/ci_phase1_smoke
python scripts/run_phase2_jump_smoke.py --out outputs/ci_phase2_jump_smoke
```

These are synthetic tests only. They do not download real data, raw images, model weights, or large archives. Automatic CI uploads compact smoke artifacts, including the generated synthetic Phase 1 report, generated synthetic Phase 2 JUMP report, JUMP smoke summary, and JUMP diagnostics summaries.

## Manual Remote JUMP Smoke

To test beyond local data, run the workflow manually from GitHub:

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **CI**.
4. Choose **Run workflow**.
5. Set `run_remote_jump_smoke` to `true`.
6. Keep `jump_plate_limit` at `1` for a small first run.

The manual remote job downloads a tiny CPJUMP1 profile subset, audits it, builds a profile index, and runs filtered diagnostics:

```bash
python scripts/download_jump_pilot_profiles.py --plate-limit 1
python scripts/audit_jump_pilot.py --summary-only --max-columns-to-print 20
python scripts/build_jump_profile_index.py
python scripts/run_jump_profile_diagnostics.py --filtered-presets
```

The job uploads only compact summary artifacts:

- JUMP inventory JSON
- index metadata JSON
- diagnostics summary CSV
- diagnostics summary JSON

It does not upload raw profiles, embeddings, full indexes, raw images, or generated parquet outputs.

## Interpretation

Automatic CI proves the software path works outside your laptop using synthetic data. The manual remote smoke proves that the public JUMP profile retrieval path can run from a fresh GitHub-hosted environment.

Neither path proves biological retrieval. Biological claims still require real-data baselines, leakage-aware diagnostics, and comparison to random/shuffled controls under meaningful splits.

## GitHub Pages Dashboard

The Pages workflow publishes only static HTML/CSS from `site/`. It does not include raw data, local outputs, embeddings, indexes, reports, model weights, or images from ignored directories.

After the workflow runs successfully, the expected public URL is:

```text
https://siamakenna.github.io/perturb-LM/
```

If that URL returns `404`, open the repository settings on GitHub, go to **Pages**, and set the source to **GitHub Actions**.
