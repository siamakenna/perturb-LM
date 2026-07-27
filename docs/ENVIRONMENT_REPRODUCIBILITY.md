# Environment Reproducibility

This project supports Python `>=3.10`. CI currently installs the package with:

```bash
python -m pip install -e ".[dev]"
```

The default dependency set intentionally excludes heavy biomedical model packages,
FAISS, torch, transformers, OpenCLIP, and BiomedCLIP. Those remain optional
modeling dependencies outside the core/dev install.

For a pinned core/dev reference environment, use:

```bash
python -m pip install -e ".[dev]" -c constraints/phase3b-ci.txt
```

For the selected Phase 3C frozen BiomedBERT compute environment, use
`docs/PHASE3C_COMPUTE_ENVIRONMENT.md`. The recommended default is Google Colab
or another Linux GPU environment, with local Windows reserved for documentation,
synthetic tests, and dry-run command validation unless it is also the actual
recorded runtime.

Phase 3C optional dependencies are installed with:

```bash
python -m pip install -e ".[phase3c,dev]" -c constraints/phase3c.txt
```

Public-safe environment report:

```bash
python scripts/print_environment_report.py
```

The report records Python, package, hardware, device, and git metadata without
including executable paths, private absolute paths, hostnames, or credential
values.

Smoke commands expected to run in a clean environment:

```bash
python -m pytest
python scripts/run_phase1_smoke.py --out outputs/phase1_smoke
python scripts/run_phase2_jump_smoke.py --out outputs/phase2_jump_smoke
python scripts/run_phase3b_projection_smoke.py --out outputs/phase3b_projection_smoke --seed 0
```

Generated files under `data/`, `outputs/`, `results/`, and `models/` remain local and ignored.
