import numpy as np
import torch

from perturb_lm.modeling.comparator_text_encoder import (
    BIOLORD_SPEC,
    MEDCPT_SPEC,
    BioLORDTextEncoder,
    MedCPTTextEncoder,
    _mean_pool_last_hidden_state,
)


def test_medcpt_contract_and_lazy_loading(tmp_path):
    encoder = MedCPTTextEncoder(tmp_path)

    assert encoder.embedding_dimension == 768
    assert encoder.spec.max_length == 64
    assert encoder.spec.pooling == "cls_last_hidden_state"
    assert encoder.spec.normalization == "none"
    assert not encoder.is_loaded
    assert MEDCPT_SPEC.revision == (
        "d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc"
    )


def test_biolord_contract_and_lazy_loading(tmp_path):
    encoder = BioLORDTextEncoder(tmp_path)

    assert encoder.embedding_dimension == 768
    assert encoder.spec.max_length == 128
    assert encoder.spec.pooling == "attention_mask_mean"
    assert encoder.spec.normalization == "l2"
    assert not encoder.is_loaded
    assert BIOLORD_SPEC.revision == (
        "167aab527b238a50ca65224e6319215d2ff4fc9f"
    )


def test_mean_pooling_ignores_padding():
    hidden = torch.tensor(
        [
            [
                [1.0, 2.0],
                [3.0, 4.0],
                [100.0, 200.0],
            ]
        ]
    )

    mask = torch.tensor([[1, 1, 0]])

    pooled = _mean_pool_last_hidden_state(
        hidden,
        mask,
    )

    np.testing.assert_allclose(
        pooled.numpy(),
        np.array([[2.0, 3.0]]),
    )
