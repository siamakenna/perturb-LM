from pathlib import Path

REQUIRED_ENGINEERING_DOCS = [
    Path("docs/PHASE3_ENGINEERING_PLAN.md"),
    Path("docs/KNOWN_GOOD_LOCAL_RUN.md"),
    Path("docs/PHASE3_ENGINEERING_TASKS.md"),
]


def test_phase3_engineering_docs_exist_and_name_data_safety_rules() -> None:
    for path in REQUIRED_ENGINEERING_DOCS:
        text = path.read_text()
        assert "raw image" in text.lower() or "raw microscopy images" in text.lower()
        assert "biological retrieval" in text.lower()
        assert "git status --short" in text


def test_known_good_run_includes_core_verification_commands() -> None:
    text = Path("docs/KNOWN_GOOD_LOCAL_RUN.md").read_text()
    required_commands = [
        "pytest",
        "scripts/run_phase1_smoke.py",
        "scripts/run_phase2_jump_smoke.py",
        "scripts/run_phase2_local_report.py",
        "scripts/check_phase2_readiness.py",
        "scripts/build_rxrx_manifests.py",
        "scripts/run_leakage_diagnostics.py",
    ]
    for command in required_commands:
        assert command in text


def test_readme_links_to_phase3_engineering_docs() -> None:
    text = Path("README.md").read_text()
    for path in REQUIRED_ENGINEERING_DOCS:
        assert path.as_posix() in text
