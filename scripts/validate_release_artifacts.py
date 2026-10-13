#!/usr/bin/env python3
"""Install exact wheel/sdist artifacts in fresh base/pixel environments and test outside source."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import venv
import xml.etree.ElementTree as ET
from pathlib import Path


def counts(path):
    result = dict(total=0, passed=0, skipped=0, failed=0, errors=0)
    for case in ET.parse(path).getroot().iter("testcase"):
        result["total"] += 1
        key = next(
            (
                key
                for tag, key in (("failure", "failed"), ("error", "errors"), ("skipped", "skipped"))
                if case.find(tag) is not None
            ),
            "passed",
        )
        result[key] += 1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--constraint", type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dist, out = args.dist.resolve(), args.out.resolve()
    if out.exists() or args.timeout <= 0:
        parser.error("Choose a new output directory and a positive timeout")
    manifest = json.loads((dist / "provenance.json").read_text())
    if manifest["status"] != "BUILT_NOT_RELEASED" or not manifest["source_unchanged"]:
        parser.error("Invalid build provenance")
    artifacts = manifest["artifacts"]
    if (
        len(artifacts) != 2
        or not any(n.endswith(".whl") for n in artifacts)
        or not any(n.endswith(".tar.gz") for n in artifacts)
    ):
        parser.error("One wheel and one source distribution required")
    for name, digest in artifacts.items():
        if (
            Path(name).name != name
            or hashlib.sha256((dist / name).read_bytes()).hexdigest() != digest
        ):
            parser.error("Artifact checksum mismatch")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "PYTEST", "PIP_"))}
    env.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PLM_EXPECT_INSTALLED="1",
    )
    constraint = ["-c", str(args.constraint.resolve())] if args.constraint else []
    out.mkdir(parents=True)
    report = {
        "schema_version": 1,
        "source_commit": manifest["source_commit"],
        "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "version": manifest["version"],
        "artifact_sha256": artifacts,
        "overall": "INCOMPLETE",
        "stages_overlap_do_not_sum_counts": True,
        "stages": {},
    }
    summary = out / "summary.json"

    def save():
        summary.write_text(json.dumps(report, indent=2) + "\n")

    save()
    for name in artifacts:
        for extra in ("base", "pixel"):
            label = ("wheel" if name.endswith(".whl") else "sdist") + "-" + extra
            start = time.monotonic()
            stage = {"status": "INCOMPLETE", "exit_code": None, "counts": None}
            xml = out / f"{label}.private.xml"
            report["stages"][label] = stage
            save()
            try:
                with tempfile.TemporaryDirectory(prefix="plm-artifact-") as temporary:
                    area = Path(temporary)
                    if area.is_relative_to(root):
                        raise RuntimeError("Artifact test directory must be outside source")
                    environment = area / "env"
                    venv.EnvBuilder(with_pip=True).create(environment)
                    binary = environment / ("Scripts" if os.name == "nt" else "bin")
                    python = binary / ("python.exe" if os.name == "nt" else "python")
                    work = area / "outside"
                    work.mkdir()
                    run_env = dict(
                        env,
                        PATH=str(binary) + os.pathsep + env.get("PATH", ""),
                        HF_HOME=str(area / "empty-model-cache"),
                    )
                    with (out / f"{label}.private.log").open("x") as log:

                        def run(command, work=work, run_env=run_env, log=log):
                            subprocess.run(
                                command,
                                cwd=work,
                                env=run_env,
                                check=True,
                                stdout=log,
                                stderr=subprocess.STDOUT,
                                timeout=args.timeout,
                            )

                        target = str(dist / name) + ("[pixel]" if extra == "pixel" else "")
                        run(
                            [
                                str(python),
                                "-I",
                                "-m",
                                "pip",
                                "install",
                                "--no-cache-dir",
                                *constraint,
                                target,
                                "pytest>=8",
                            ]
                        )
                        run([str(python), "-I", "-m", "pip", "check"])
                        # Check import origin, metadata agreement and base isolation.
                        probe = (
                            "import importlib.metadata as m, importlib.util as u, sys; "
                            "from pathlib import Path; import perturb_lm; "
                            "assert Path(perturb_lm.__file__).is_relative_to(Path(sys.prefix)); "
                            f"assert m.version('perturb-lm') == {manifest['version']!r}; "
                            "assert not any('src/perturb_lm' in p for p in sys.path); "
                            "assert u.find_spec('torch') is None; "
                            "assert u.find_spec('transformers') is None; "
                            + (
                                "assert u.find_spec('skimage') is None; "
                                "assert u.find_spec('tifffile') is None"
                                if extra == "base"
                                else "assert u.find_spec('skimage') is not None"
                            )
                        )
                        run([str(python), "-I", "-c", probe])
                        versions = subprocess.check_output(
                            [
                                str(python),
                                "-I",
                                "-c",
                                "import importlib.metadata as m, json, platform; "
                                "print(json.dumps({'python': platform.python_version(), "
                                "'packages': {n: m.version(n) for n in "
                                "['perturb-lm', 'scikit-learn', 'numpy', 'pandas', 'pytest']}}))",
                            ],
                            cwd=work,
                            env=run_env,
                            text=True,
                            timeout=args.timeout,
                        )
                        stage["environment"] = json.loads(versions)
                        shutil.copyfile(
                            root / "tests/test_release_contract.py", work / "test_api.py"
                        )
                        documents = ["PACKAGE_API.md"]
                        if extra == "pixel":
                            documents.append("PIXEL_PACKAGE_EXAMPLE.md")
                        blocks = []
                        for document in documents:
                            blocks.extend(
                                re.findall(
                                    r"```python\n(.*?)```",
                                    (root / "docs" / document).read_text(),
                                    re.S,
                                )
                            )
                        if len(blocks) != len(documents):
                            raise RuntimeError("Expected one executable example per document")
                        (work / "test_examples.py").write_text(
                            "\n".join(
                                f"def test_example_{i}():\n    exec({code!r}, {{}})\n"
                                for i, code in enumerate(blocks)
                            )
                        )
                        (work / "pytest.ini").write_text("[pytest]\n")
                        run(
                            [
                                str(python),
                                "-I",
                                "-m",
                                "pytest",
                                "-q",
                                "-c",
                                "pytest.ini",
                                f"--junitxml={xml}",
                                "test_api.py",
                                "test_examples.py",
                            ]
                        )
                        stage["counts"] = counts(xml)
                        if (
                            stage["counts"]["skipped"]
                            or stage["counts"]["failed"]
                            or stage["counts"]["errors"]
                        ):
                            raise RuntimeError("Artifact acceptance requires all tests to pass")
                        stage.update(status="PASS", exit_code=0)
            except (subprocess.SubprocessError, OSError, RuntimeError) as error:
                if xml.exists():
                    stage["counts"] = counts(xml)
                stage.update(
                    status="REVIEW_REQUIRED",
                    exit_code=getattr(error, "returncode", None),
                    error_type=type(error).__name__,
                )
                report["overall"] = "REVIEW_REQUIRED"
                save()
                raise SystemExit(f"{label} failed; inspect its local private log") from error
            stage["elapsed_seconds"] = round(time.monotonic() - start, 2)
            save()
            print(f"{label}: PASS {stage['counts']}", flush=True)
    report["overall"] = "PASS"
    save()


if __name__ == "__main__":
    main()
