"""Build and install a wheel; execute its CLI outside the source checkout."""

import json
import os
import subprocess
import sys
import sysconfig
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    area = tmp_path_factory.mktemp("installed_pixel")
    wheels = area / "wheels"
    wheels.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--no-cache-dir",
            "--wheel-dir",
            str(wheels),
            str(ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    environment = area / "environment"
    venv.EnvBuilder(with_pip=True).create(environment)
    bindir = environment / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    # Reuse already installed dependencies without processing the checkout's editable .pth.
    purelib = Path(
        subprocess.check_output(
            [str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
            text=True,
        ).strip()
    )
    (purelib / "test_dependencies.pth").write_text(sysconfig.get_path("purelib") + "\n")
    wheel = next(wheels.glob("perturb_lm-*.whl"))
    subprocess.run(
        [
            str(python),
            "-I",
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--ignore-installed",
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    outside = area / "outside"
    outside.mkdir()
    env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    probe = subprocess.check_output(
        [
            str(python),
            "-I",
            "-c",
            "import perturb_lm.images.pixel_workflow as m; print(m.__file__)",
        ],
        cwd=outside,
        env=env,
        text=True,
    ).strip()
    assert Path(probe).is_relative_to(environment)
    assert not Path(probe).is_relative_to(ROOT)
    return python, bindir / ("perturb-lm.exe" if os.name == "nt" else "perturb-lm"), outside, env


def test_installed_cli_analyze_fit_search_and_demo(installed):
    python, cli, outside, env = installed
    fixture = """
from pathlib import Path
from tifffile import imwrite
from perturb_lm.images.pixel_demo import make_images
images = make_images()
for i in (0, 1, 2, 8):
    imwrite(Path(f'image_{i}.tif'), images[i], photometric='minisblack')
"""
    subprocess.run([str(python), "-I", "-c", fixture], cwd=outside, env=env, check=True)
    common = ["--axes", "CYX", "--channels", "c0,c1,c2"]
    commands = [
        ["version"],
        ["images", "analyze", "image_8.tif", *common, "--out", "analysis"],
        [
            "images",
            "fit",
            "image_0.tif",
            "image_1.tif",
            "image_2.tif",
            *common,
            "--image-id",
            "r0",
            "--image-id",
            "r1",
            "--image-id",
            "r2",
            "--out",
            "reference",
        ],
        [
            "images",
            "search",
            "image_8.tif",
            *common,
            "--reference",
            "reference",
            "--image-id",
            "q8",
            "--top-k",
            "2",
            "--out",
            "query",
        ],
        [
            "images",
            "analyze",
            "image_8.tif",
            *common,
            "--state",
            "reference/state.json",
            "--out",
            "scaled_analysis",
        ],
    ]
    for command in commands:
        process = subprocess.run(
            [str(cli), *command], cwd=outside, env=env, capture_output=True, text=True
        )
        assert process.returncode == 0, process.stdout + process.stderr
    assert (outside / "query/report.html").is_file()
    assert (outside / "query/measurements.csv").is_file()
    assert (outside / "query/masks/000000.tif").is_file()
    assert (outside / "query/scaled_features.csv").is_file()
    assert json.loads((outside / "reference/run.json").read_text())["n_accepted"] == 3
    subprocess.run(
        [str(python), "-I", "-m", "perturb_lm.images.pixel_demo", "--out", "demo"],
        cwd=outside,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert (outside / "demo/object_overlay.png").exists()
