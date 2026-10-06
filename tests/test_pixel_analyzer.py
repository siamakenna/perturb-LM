import numpy as np
import pytest
from sklearn.base import clone
from sklearn.exceptions import NotFittedError
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from perturb_lm.images.pixel_analyzer import PixelMorphologyTransformer


def image(radius=5):
    yy, xx = np.mgrid[:64, :64]
    signal = np.zeros((64, 64), dtype=np.uint16)
    for y, x in ((16, 16), (16, 46), (46, 16), (46, 46)):
        signal[((yy - y) ** 2 + (xx - x) ** 2) <= radius**2] = 2000
    return np.stack([signal, signal // 2])


@pytest.fixture
def images():
    return np.stack([image(r) for r in (3, 4, 5, 6)])


def test_features_and_four_objects(images):
    m = PixelMorphologyTransformer(scale_features=False).fit(images)
    x = m.transform(images)
    assert x.shape == (4, 21)
    np.testing.assert_array_equal(x[:, 0], [4, 4, 4, 4])
    assert np.isfinite(x).all()
    assert len(m.get_feature_names_out()) == x.shape[1]


def test_clone_unfitted(images):
    m = PixelMorphologyTransformer().fit(images)
    copy = clone(m)
    assert copy.get_params() == m.get_params()
    with pytest.raises(NotFittedError):
        copy.transform(images)


def test_pipeline(images):
    pipe = Pipeline(
        [("pixels", PixelMorphologyTransformer(scale_features=False)), ("scale", StandardScaler())]
    )
    assert pipe.fit_transform(images).shape == (4, 21)


def test_no_y_identity_effect(images):
    a = PixelMorphologyTransformer().fit(images, ["geneA"] * 4)
    b = PixelMorphologyTransformer().fit(images, ["unrelated"] * 4)
    np.testing.assert_array_equal(a.transform(images), b.transform(images))


def test_no_metadata_or_filename_arguments(images):
    with pytest.raises(TypeError):
        PixelMorphologyTransformer().fit(images, metadata={"gene": "A"})
    with pytest.raises(TypeError):
        PixelMorphologyTransformer().fit({"image": images, "gene": "A"})
    with pytest.raises(ValueError):
        PixelMorphologyTransformer().fit(["geneA_plate1.tif"])


def test_renaming_files_does_not_change_features(images, tmp_path):
    a, b = tmp_path / "geneA.npy", tmp_path / "other_experiment.npy"
    np.save(a, images, allow_pickle=False)
    np.save(b, images, allow_pickle=False)
    m = PixelMorphologyTransformer().fit(images)
    np.testing.assert_array_equal(
        m.transform(np.load(a, allow_pickle=False)), m.transform(np.load(b, allow_pickle=False))
    )


def test_train_only_scaler_and_no_mutation(images):
    original = images.copy()
    m = PixelMorphologyTransformer().fit(images[:2])
    mean = m.scaler_.mean_.copy()
    m.transform(images[2:] * 2)
    np.testing.assert_array_equal(mean, m.scaler_.mean_)
    np.testing.assert_array_equal(images, original)


def test_row_permutation(images):
    m = PixelMorphologyTransformer().fit(images)
    np.testing.assert_array_equal(m.transform(images[::-1]), m.transform(images)[::-1])


def test_pixels_actually_matter(images):
    m = PixelMorphologyTransformer(scale_features=False).fit(images)
    assert not np.array_equal(m.transform(images[:1]), m.transform(images[:1] * 2))


def test_blank(images):
    blank = np.zeros_like(images)
    with pytest.raises(ValueError, match="constant"):
        PixelMorphologyTransformer().fit(blank)


def test_wrong_channel_count(images):
    m = PixelMorphologyTransformer().fit(images)
    with pytest.raises(ValueError, match="Channel count"):
        m.transform(images[:, :1])


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((4, 64, 64)),
        np.full((1, 2, 64, 64), np.nan),
        np.full((1, 2, 64, 64), np.inf),
        np.array([]),
        np.zeros((1, 2, 4, 4)),
    ],
)
def test_bad_inputs(bad):
    with pytest.raises(ValueError):
        PixelMorphologyTransformer().fit(bad)


@pytest.mark.parametrize(
    "params",
    [
        {"segmentation_channel": 4},
        {"min_object_area": 0},
        {"smooth_sigma": -1},
        {"min_peak_distance": 0},
    ],
)
def test_bad_parameters(params, images):
    with pytest.raises(ValueError):
        PixelMorphologyTransformer(**params).fit(images)


@pytest.mark.parametrize("axes", ["CYX", "YXC", "YX"])
def test_tiff_pixels_and_renamed_files(axes, images, tmp_path):
    from tifffile import imwrite

    from perturb_lm.images.pixel_analyzer import read_tiff_chw

    original = images[0]
    stored = (
        original
        if axes == "CYX"
        else (np.moveaxis(original, 0, -1) if axes == "YXC" else original[0])
    )
    expected = original if axes != "YX" else original[:1]
    a, b = tmp_path / "geneA.tif", tmp_path / "anonymous.tif"
    for path in (a, b):
        imwrite(path, stored, photometric="minisblack")
        loaded = read_tiff_chw(path, axes=axes)
        assert loaded.dtype == original.dtype
        np.testing.assert_array_equal(loaded, expected)


def test_tiff_axes_not_guessed(tmp_path):
    from perturb_lm.images.pixel_analyzer import read_tiff_chw

    with pytest.raises(ValueError, match="explicit axes"):
        read_tiff_chw(tmp_path / "unused.tif", axes="TCZYX")
