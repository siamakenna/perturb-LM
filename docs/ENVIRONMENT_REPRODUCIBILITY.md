# Environment Reproducibility

This project supports Python `>=3.10`. CI currently installs the package with:

```bash
python -m pip install -e ".[dev]"
```

The default dependency set intentionally excludes heavy biomedical model packages, FAISS, torch, transformers, OpenCLIP, and BiomedCLIP. Those remain optional future modeling dependencies.

For a pinned core/dev reference environment, use:

```bash
python -m pip install -e ".[dev]" -c constraints/phase3b-ci.txt
```

Public-safe environment report:

```bash
python scripts/print_environment_report.py
```

Smoke commands expected to run in a clean environment:

```bash
python -m pytest
python scripts/run_phase1_smoke.py --out outputs/phase1_smoke
python scripts/run_phase2_jump_smoke.py --out outputs/phase2_jump_smoke
python scripts/run_phase3b_projection_smoke.py --out outputs/phase3b_projection_smoke --seed 0
```

Generated files under `data/`, `outputs/`, `results/`, and `models/` remain local and ignored.
