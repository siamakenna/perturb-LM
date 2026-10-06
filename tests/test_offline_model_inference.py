"""Real offline forward passes on locally generated random DINOv2/BERT fixtures.

No pretrained weights, network requests, asset downloads or biological claims.
This file requires the existing phase3c extra and must run in Linux source CI.
"""

import inspect
import json
import pickle
import socket
from dataclasses import replace

import numpy as np
import pytest
import torch
from sklearn.base import clone
from transformers import BertConfig, BertModel, BertTokenizerFast, Dinov2Config, Dinov2Model

from perturb_lm.sklearn_api import ImagePreprocessing, LocalModelEmbedder, asset_catalog
from perturb_lm.sklearn_api.datasets import file_checksum


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "empty-hf"))

    def deny(*args, **kwargs):
        raise AssertionError("Synthetic adapter tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", deny)
    torch.manual_seed(17)
    torch.set_num_threads(1)


@pytest.fixture
def assets(tmp_path):
    result = {}
    for family in ("dinov2", "sapbert"):
        path = tmp_path / family
        path.mkdir()
        spec = replace(
            asset_catalog()[family],
            identifier=f"synthetic/{family}",
            revision="0" * 40,
            dimension=24,
            input_shape=(3, 28, 28) if family == "dinov2" else (),
            max_length=12,
        )
        if family == "dinov2":
            model = Dinov2Model(
                Dinov2Config(
                    image_size=28,
                    patch_size=14,
                    num_channels=3,
                    hidden_size=24,
                    num_hidden_layers=1,
                    num_attention_heads=3,
                    mlp_ratio=2,
                )
            )
        else:
            vocabulary = [
                "[PAD]",
                "[UNK]",
                "[CLS]",
                "[SEP]",
                "[MASK]",
                "cell",
                "nucleus",
                "large",
                "small",
                "bright",
                "round",
            ]
            (path / "vocab.txt").write_text("\n".join(vocabulary) + "\n")
            BertTokenizerFast(vocab_file=str(path / "vocab.txt")).save_pretrained(path)
            model = BertModel(
                BertConfig(
                    vocab_size=len(vocabulary),
                    hidden_size=24,
                    num_hidden_layers=1,
                    num_attention_heads=3,
                    intermediate_size=32,
                    max_position_embeddings=32,
                    hidden_dropout_prob=0.3,
                    attention_probs_dropout_prob=0.3,
                )
            )
        model.save_pretrained(path, safe_serialization=True)
        checksums = {p.name: file_checksum(p) for p in path.iterdir() if p.is_file()}
        (path / "asset.json").write_text(
            json.dumps(
                {
                    "identifier": spec.identifier,
                    "revision": spec.revision,
                    "complete": True,
                    "synthetic": True,
                    "checksums": checksums,
                }
            )
        )
        result[family] = (spec, path)
    return result


def config():
    return ImagePreprocessing(
        input_channels=("c0", "c1", "c2", "c3"),
        model_channels=("c2", "c0", "c3"),
        input_range=(0.0, 100.0),
        mean=(0.5, 0.4, 0.3),
        std=(0.2, 0.3, 0.4),
    )


def norm(v):
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_preprocessing_fixed_range_channel_order_and_no_input_mutation():
    pixels = np.stack([np.full((4, 6), x) for x in (20, 99, 50, 90)])[None]
    before = pixels.copy()
    tensor = config().tensor(pixels, (28, 28), torch).numpy()
    expected = (np.array([50, 20, 90]) / 100 - [0.5, 0.4, 0.3]) / [0.2, 0.3, 0.4]
    np.testing.assert_allclose(tensor[0, :, 14, 14], expected, atol=1e-6)
    assert tensor.shape == (1, 3, 28, 28)
    np.testing.assert_array_equal(pixels, before)


def test_actual_dinov2_pixels_cls_channel_ablations_and_order(assets):
    spec, path = assets["dinov2"]
    pixels = np.random.default_rng(2).uniform(0, 100, (3, 4, 30, 34)).astype("float32")
    before = pixels.copy()
    adapter = LocalModelEmbedder(spec, path, batch_size=2, image_preprocessing=config())
    assert not hasattr(adapter.fit(pixels, y=["external"] * 3), "backend_")
    fitted_state = pickle.dumps(adapter)
    result = adapter.transform(pixels)
    assert pickle.dumps(adapter) == fitted_state
    direct = Dinov2Model.from_pretrained(path, local_files_only=True, use_safetensors=True).eval()
    with torch.inference_mode():
        expected = direct(pixel_values=config().tensor(pixels, (28, 28), torch)).last_hidden_state[
            :, 0
        ]
    np.testing.assert_allclose(result, norm(expected.numpy()), atol=1e-6)
    np.testing.assert_allclose(adapter.transform(pixels[::-1].copy()), result[::-1], atol=1e-6)
    unselected = pixels.copy()
    unselected[:, 1] = 0
    np.testing.assert_allclose(adapter.transform(unselected), result, atol=1e-6)
    changed = pixels.copy()
    changed[:, 2] = 0
    assert np.max(np.abs(adapter.transform(changed) - result)) > 1e-4
    np.testing.assert_array_equal(pixels, before)
    np.testing.assert_allclose(
        clone(adapter).fit(pixels[:1], y=["different"]).transform(pixels), result, atol=1e-6
    )
    model = inspect.getclosurevars(adapter.backend_).nonlocals["model"]
    weights = {k: v.clone() for k, v in model.state_dict().items()}
    adapter.transform(changed)
    assert not model.training and all(not p.requires_grad for p in model.parameters())
    assert all(torch.equal(weights[k], v) for k, v in model.state_dict().items())
    np.testing.assert_allclose(pickle.loads(pickle.dumps(adapter)).transform(pixels), result)


def test_actual_sapbert_cls_padding_truncation_batching_and_state(assets):
    spec, path = assets["sapbert"]
    text = ["large cell", "small round nucleus", "bright cell " * 20]
    adapter = LocalModelEmbedder(spec, path, batch_size=2).fit(text[:1])
    fitted_state = pickle.dumps(adapter)
    result = adapter.transform(text)
    assert pickle.dumps(adapter) == fitted_state
    tokenizer = BertTokenizerFast.from_pretrained(path, local_files_only=True)
    encoded = tokenizer(text, padding=True, truncation=True, max_length=12, return_tensors="pt")
    assert encoded["input_ids"].shape[1] == 12
    direct = BertModel.from_pretrained(path, local_files_only=True, use_safetensors=True).eval()
    with torch.inference_mode():
        expected = direct(**encoded).last_hidden_state[:, 0].numpy()
    np.testing.assert_allclose(result, norm(expected), atol=1e-6)
    np.testing.assert_allclose(adapter.transform(text[::-1]), result[::-1], atol=1e-6)
    np.testing.assert_allclose(
        clone(adapter).set_params(batch_size=1).fit_transform(text), result, atol=1e-6
    )
    assert np.max(np.abs(result[0] - result[1])) > 1e-5
    np.testing.assert_allclose(
        pickle.loads(pickle.dumps(adapter)).transform(text), result, atol=1e-6
    )
    with pytest.raises(ValueError, match="strings"):
        adapter.transform([""])


def test_cache_contract_and_tamper_rejection(assets, tmp_path, monkeypatch):
    spec, path = assets["dinov2"]
    pixels = np.full((1, 4, 28, 28), 30.0)
    cache = tmp_path / "cache"
    adapter = LocalModelEmbedder(spec, path, cache, image_preprocessing=config()).fit(pixels)
    original = adapter.transform(pixels)
    modified = replace(config(), model_channels=("c0", "c3", "c2"))
    other = clone(adapter).set_params(image_preprocessing=modified).fit(pixels)
    other.transform(pixels)
    assert len(list(cache.iterdir())) == 2

    def deny(*args):
        raise AssertionError("Cached output must not reload weights")

    monkeypatch.setattr("perturb_lm.sklearn_api.model_assets.load_backend", deny)
    np.testing.assert_array_equal(clone(adapter).fit(pixels).transform(pixels), original)
    (path / "config.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        adapter.transform(pixels)


@pytest.mark.parametrize("family", ["dinov2", "sapbert"])
def test_dimension_mismatch_fails_before_inference(assets, family):
    spec, path = assets[family]
    bad = replace(spec, dimension=25)
    X = np.zeros((1, 4, 28, 28)) if family == "dinov2" else ["cell"]
    with pytest.raises(ValueError, match="architecture/dimension"):
        LocalModelEmbedder(
            bad,
            path,
            image_preprocessing=config() if family == "dinov2" else None,
        ).fit_transform(X)


def test_missing_weights_are_not_silently_randomly_initialized(assets):
    from safetensors.torch import load_file, save_file

    spec, path = assets["sapbert"]
    weights = path / "model.safetensors"
    state = load_file(weights)
    del state["embeddings.word_embeddings.weight"]
    save_file(state, weights, metadata={"format": "pt"})
    # This is a checksummed but semantically incomplete synthetic checkpoint.
    manifest = json.loads((path / "asset.json").read_text())
    manifest["checksums"]["model.safetensors"] = file_checksum(weights)
    (path / "asset.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="weights do not exactly match"):
        LocalModelEmbedder(spec, path).fit_transform(["cell"])
