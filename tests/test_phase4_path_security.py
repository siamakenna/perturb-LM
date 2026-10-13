"""Filesystem-boundary regressions with private, synthetic temporary files only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import comparator_tools as c
import prepare_native_launch as launcher


@pytest.mark.parametrize("command", ["analyze", "compare", "scores", "prepare-images"])
def test_output_parent_alias_cannot_redirect_writes(tmp_path, monkeypatch, command):
    selected = tmp_path / "selected with spaces"
    other = tmp_path / "other"
    selected.mkdir()
    other.mkdir()
    alias = tmp_path / "directory alias"
    alias.symlink_to(selected, target_is_directory=True)
    victim = other / "output"
    victim.mkdir()
    sentinel = victim / "cosine.private.npz"
    sentinel.write_bytes(b"existing output must not be overwritten")
    new_output = c.new_output

    def retarget_after_creation(path):
        result = new_output(path)
        alias.unlink()
        alias.symlink_to(other, target_is_directory=True)
        return result

    monkeypatch.setattr(c, "new_output", retarget_after_creation)
    archive = tmp_path / "features.npz"
    np.savez(archive, features=np.eye(3), record_ids=np.array(["a", "b", "c"]))
    output = alias / "output"
    if command == "analyze":
        c.analyze(archive, "auto", "auto", output, 1, None, False, False)
    elif command == "compare":
        c.compare(
            [[n, str(archive), "auto", "auto"] for n in ("a", "b")], "image", "synthetic", output, 1
        )
    elif command == "scores":
        scores = tmp_path / "scores.tsv"
        scores.write_text("method\tquery_id\tevaluable\taverage_precision\na\tq\ttrue\t1\n")
        c.scores_summary(
            scores,
            output,
            "method",
            "query_id",
            "evaluable",
            "average_precision",
            "synthetic",
            "\t",
        )
    else:
        data = tmp_path / "data"
        data.mkdir()
        tifffile.imwrite(
            data / "image.tif",
            np.ones((3, 8, 8), dtype=np.uint16),
            photometric="minisblack",
            metadata={"axes": "CYX"},
        )
        selection = tmp_path / "selection.json"
        selection.write_text(json.dumps([{"record_id": "one", "path": "image.tif"}]))
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "axes": "CYX",
                    "preprocessing": {
                        "input_channels": ["a", "b", "c"],
                        "model_channels": ["a", "b", "c"],
                        "input_range": [0, 255],
                        "mean": [0, 0, 0],
                        "std": [1, 1, 1],
                    },
                }
            )
        )
        c.prepare_images(selection, data, settings, output)
    assert sentinel.read_bytes() == b"existing output must not be overwritten"
    assert list(victim.iterdir()) == [sentinel]
    assert (selected / "output/analysis-complete.json").is_file()


def test_analysis_archive_refuses_a_file_created_after_directory_creation(tmp_path, monkeypatch):
    archive = tmp_path / "features.npz"
    np.savez(archive, features=np.eye(2), record_ids=np.array(["a", "b"]))
    output = tmp_path / "output"
    new_output = c.new_output

    def insert_existing_file(path):
        result = new_output(path)
        (result / "cosine.private.npz").write_bytes(b"preserve me")
        return result

    monkeypatch.setattr(c, "new_output", insert_existing_file)
    with pytest.raises(FileExistsError):
        c.analyze(archive, "auto", "auto", output, 1, None, False, False)
    assert (output / "cosine.private.npz").read_bytes() == b"preserve me"
    assert not (output / "analysis-complete.json").exists()


@pytest.mark.parametrize("kind", ["image", "inventory"])
@pytest.mark.parametrize("escape", ["parent", "absolute", "sibling-prefix", "symlink"])
def test_inventory_paths_cannot_read_outside_the_selected_root(tmp_path, kind, escape):
    root = (tmp_path / "data").resolve()
    root.mkdir()
    sibling = root.with_name("data-other")
    sibling.mkdir()
    outside = sibling / ("image.tif" if kind == "image" else "inventory.json")
    outside.write_bytes(b"outside input")
    if escape == "parent":
        relative = "../data-other/" + outside.name
    elif escape == "absolute":
        relative = str(outside)
    elif escape == "sibling-prefix":
        (root / "link").symlink_to(sibling, target_is_directory=True)
        relative = "link/" + outside.name
    else:
        (root / outside.name).symlink_to(outside)
        relative = outside.name
    validate = c.confined_file if kind == "image" else launcher.confined_inventory
    with pytest.raises(ValueError):
        validate(root, relative)


@pytest.mark.parametrize("kind", ["image", "inventory"])
def test_confined_paths_accept_in_root_aliases_and_spaces(tmp_path, kind):
    root = tmp_path.resolve()
    folder = root / "directory with spaces"
    folder.mkdir()
    filename = "image.tif" if kind == "image" else "inventory.json"
    expected = folder / filename
    expected.write_bytes(b"synthetic input")
    (root / "alias").symlink_to(folder, target_is_directory=True)
    validate = c.confined_file if kind == "image" else launcher.confined_inventory
    assert validate(root, "alias/" + filename) == expected


@pytest.mark.parametrize("existing", ["file", "directory", "dangling-symlink"])
def test_fresh_output_rejects_existing_entries_without_touching_them(tmp_path, existing):
    path = tmp_path / "output"
    if existing == "file":
        path.write_bytes(b"existing")
    elif existing == "directory":
        path.mkdir()
    else:
        path.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError):
        c.new_output(path)
    assert path.is_symlink() if existing == "dangling-symlink" else path.exists()
    assert not (tmp_path / "missing").exists()


def test_request_prompt_cannot_redirect_output_by_retargeting_parent(tmp_path, monkeypatch):
    selected = tmp_path / "selected"
    other = tmp_path / "other"
    selected.mkdir()
    other.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(selected, target_is_directory=True)
    record = tmp_path / "record.json"
    record.write_text("{}")
    responses = {
        "approval": record,
        "manifest": record,
        "asset_root": tmp_path,
        "data_root": tmp_path,
        "pilot_output": tmp_path / "future output",
    }

    def respond(prompt):
        key = prompt.removesuffix(": ")
        if key == "pilot_output":
            alias.unlink()
            alias.symlink_to(other, target_is_directory=True)
        return str(responses[key])

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", respond)
    launcher.make_request(alias / "request.json")
    assert (selected / "request.json").is_file()
    assert list(other.iterdir()) == []
