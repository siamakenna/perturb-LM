import numpy as np
import pytest

from perturb_lm.modeling.text_encoder import (
    BIOMEDBERT_EMBEDDING_DIMENSION,
    FrozenBiomedicalTextEncoder,
    DeterministicFakeTextEncoder,
    validate_embedding_matrix,
)


def test_fake_text_encoder_is_deterministic_and_finite():
    encoder = DeterministicFakeTextEncoder(seed=7, embedding_dimension_value=5)
    first = encoder.encode(["mitochondrial organization", "lysosomal stress"])
    second = encoder.encode(["mitochondrial organization", "lysosomal stress"])
    assert first.shape == (2, 5)
    np.testing.assert_allclose(first, second)
    assert np.isfinite(first).all()


def test_frozen_biomedical_encoder_is_lazy():
    encoder = FrozenBiomedicalTextEncoder()
    assert not encoder.is_loaded
    assert encoder.embedding_dimension == BIOMEDBERT_EMBEDDING_DIMENSION


def test_embedding_validation_rejects_bad_dimensions_and_nonfinite_values():
    validate_embedding_matrix(np.ones((2, 3)), expected_dim=3)
    with pytest.raises(ValueError, match="dimension"):
        validate_embedding_matrix(np.ones((2, 4)), expected_dim=3)
    with pytest.raises(ValueError, match="NaN|infinite"):
        validate_embedding_matrix(np.array([[1.0, np.nan]]), expected_dim=2)
