"""Pixel-only morphology baseline. No biological metadata or model downloads.

Images have (channels, height, width) axes. Batches are (N, C, H, W),
or sequences of numeric CHW arrays. This is a 2-D object-segmentation
baseline, not a validated cell/nucleus classifier or a clinical tool.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.filters import threshold_otsu
from skimage.measure import regionprops
from skimage.segmentation import watershed
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

FEATURE_SCHEMA = "pixel-morphology-v1"


class PixelInputError(ValueError):
    """A rejected observation with a machine-readable QC reason."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class PixelMorphologyTransformer(TransformerMixin, BaseEstimator):
    """Extract image/object measurements and optionally fit a train-only scaler.

    Parameters describe image interpretation, not treatment identity. Channel
    index 0 is not presumed to be DNA. Caller must choose a suitable channel.
    Pixel units are reported; physical units require separately supplied calibration.
    The optional y argument is ignored, as in an unsupervised transformer.
    """

    def __init__(
        self,
        *,
        segmentation_channel=0,
        min_object_area=8,
        smooth_sigma=1.0,
        min_peak_distance=4,
        scale_features=True,
    ):
        self.segmentation_channel = segmentation_channel
        self.min_object_area = min_object_area
        self.smooth_sigma = smooth_sigma
        self.min_peak_distance = min_peak_distance
        self.scale_features = scale_features

    def _validate_parameters(self):
        for name, lower in (
            ("segmentation_channel", 0),
            ("min_object_area", 1),
            ("min_peak_distance", 1),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, (bool, np.bool_))
                or not isinstance(value, (int, np.integer))
                or value < lower
            ):
                raise ValueError(f"{name} must be an integer >= {lower}.")
        if (
            not isinstance(self.smooth_sigma, (int, float, np.integer, np.floating))
            or not np.isfinite(self.smooth_sigma)
            or self.smooth_sigma < 0
        ):
            raise ValueError("smooth_sigma must be finite and nonnegative.")
        if not isinstance(self.scale_features, (bool, np.bool_)):
            raise ValueError("scale_features must be boolean.")

    def _images(self, X, *, check_signal=True):
        self._validate_parameters()
        if isinstance(X, np.ndarray):
            if X.ndim != 4:
                raise ValueError("Expected a batch shaped (N, C, H, W).")
            images = list(X)
        elif isinstance(X, (list, tuple)):
            images = list(X)
        else:
            raise TypeError("Pass numeric image arrays, not metadata tables or paths.")
        if not images:
            raise ValueError("Image batch is empty.")
        channels = None
        checked = []
        for image in images:
            if not isinstance(image, np.ndarray) or image.ndim != 3:
                raise PixelInputError("incompatible_axes", "Each image must be a CHW NumPy array.")
            if image.dtype.kind not in "uif" or not np.isfinite(image).all():
                raise PixelInputError(
                    "nonfinite_or_nonnumeric", "Images must contain finite, real numeric pixels."
                )
            if image.shape[0] < 1 or min(image.shape[1:]) < 8:
                raise PixelInputError(
                    "incompatible_shape", "Require at least one channel and spatial axes >= 8."
                )
            if channels is None:
                channels = image.shape[0]
            if image.shape[0] != channels:
                raise PixelInputError(
                    "incompatible_channels", "All images must have the same channel count."
                )
            if self.segmentation_channel >= channels:
                raise PixelInputError(
                    "incompatible_channels", "segmentation_channel is outside the image channels."
                )
            plane = image[self.segmentation_channel]
            if check_signal and plane.min() == plane.max():
                raise PixelInputError(
                    "blank", "Segmentation channel is constant; observation excluded."
                )
            checked.append(image)
        return checked

    def _segment(self, image):
        plane = image[self.segmentation_channel].astype(np.float64, copy=True)
        lo, hi = np.quantile(plane, [0.01, 0.99])
        if hi <= lo:
            lo, hi = float(plane.min()), float(plane.max())
        # Segmentation/display normalization does not replace raw measurements.
        plane = np.clip((plane - lo) / (hi - lo), 0, 1)
        plane = ndi.gaussian_filter(plane, sigma=self.smooth_sigma)
        mask = plane > threshold_otsu(plane)
        components, _ = ndi.label(mask)
        sizes = np.bincount(components.ravel())
        keep = sizes >= self.min_object_area
        keep[0] = False
        mask = keep[components]
        if not mask.any():
            return np.zeros(mask.shape, dtype=np.int32)
        distance = ndi.distance_transform_edt(mask)
        peaks = peak_local_max(
            distance,
            labels=mask.astype(np.uint8),
            min_distance=self.min_peak_distance,
            exclude_border=False,
        )
        markers = np.zeros(mask.shape, dtype=np.int32)
        if len(peaks):
            markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
        # Ensure every connected component has at least one marker.
        components, count = ndi.label(mask)
        next_id = int(markers.max())
        for component in range(1, count + 1):
            part = components == component
            if not markers[part].any():
                pos = np.unravel_index(np.argmax(np.where(part, distance, -1)), mask.shape)
                next_id += 1
                markers[pos] = next_id
        labels = watershed(-distance, markers, mask=mask)
        sizes = np.bincount(labels.ravel())
        ids = np.flatnonzero(sizes >= self.min_object_area)
        ids = ids[ids != 0]
        mapping = np.zeros(len(sizes), dtype=np.int32)
        mapping[ids] = np.arange(1, len(ids) + 1)
        return mapping[labels]

    @staticmethod
    def _names(channels):
        names = [
            "object_count",
            "foreground_fraction",
            "object_area_mean_px",
            "object_area_std_px",
            "object_eccentricity_mean",
            "object_solidity_mean",
            "object_perimeter_mean_px",
        ]
        for channel in range(channels):
            names.extend(
                f"channel_{channel}_{name}"
                for name in (
                    "mean",
                    "std",
                    "p10",
                    "median",
                    "p90",
                    "gradient_energy",
                    "nonzero_fraction",
                )
            )
        return np.asarray(names, dtype=object)

    def _features(self, image):
        labels = self._segment(image)
        return self._features_from_mask(image, labels)

    def _features_from_mask(self, image, labels):
        regions = regionprops(labels)
        area = np.asarray([r.area for r in regions], float)
        values = [
            len(regions),
            np.mean(labels > 0),
            area.mean() if len(area) else 0,
            area.std() if len(area) else 0,
        ]
        for attribute in ("eccentricity", "solidity", "perimeter"):
            values.append(np.mean([getattr(r, attribute) for r in regions]) if regions else 0)
        for channel in image:
            pixels = channel.astype(np.float64)
            q10, q50, q90 = np.quantile(pixels, [0.1, 0.5, 0.9])
            gradient = np.mean(np.diff(pixels, axis=0) ** 2) + np.mean(np.diff(pixels, axis=1) ** 2)
            values.extend(
                [pixels.mean(), pixels.std(), q10, q50, q90, gradient, np.mean(pixels != 0)]
            )
        result = np.asarray(values, dtype=np.float64)
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite features; check image intensity range.")
        return result

    def measure(self, image):
        """Return raw features, object labels and per-object pixel measurements.

        No fit or metadata is required. Areas are pixel squared, perimeter and
        centroids are pixels, intensities retain decoded source units.
        """
        image = self._images([image])[0]
        labels = self._segment(image)
        objects = []
        for region in regionprops(labels):
            row = {
                "object_id": int(region.label),
                "area_px2": float(region.area),
                "perimeter_px": float(region.perimeter),
                "centroid_y_px": float(region.centroid[0]),
                "centroid_x_px": float(region.centroid[1]),
                "eccentricity": float(region.eccentricity),
                "solidity": float(region.solidity),
            }
            for c, plane in enumerate(image):
                pixels = plane[labels == region.label].astype(float)
                row[f"channel_{c}_mean_intensity"] = float(pixels.mean())
                row[f"channel_{c}_sum_intensity"] = float(pixels.sum())
            objects.append(row)
        return self._features_from_mask(image, labels), labels, objects

    @staticmethod
    def feature_units(channels):
        """Units aligned with the stable v1 names (legacy area suffix is _px)."""
        units = [
            "count",
            "fraction",
            "pixel^2",
            "pixel^2",
            "dimensionless",
            "dimensionless",
            "pixel",
        ]
        for _ in range(channels):
            units.extend(["source_intensity"] * 5 + ["source_intensity^2/pixel^2", "fraction"])
        return units

    def fit(self, X, y=None):
        """Learn only feature-scaling statistics from training images."""
        self.__dict__.pop("feature_names_out_", None)
        images = self._images(X)
        features = np.stack([self._features(image) for image in images])
        scaler = StandardScaler().fit(features) if self.scale_features else None
        self.n_channels_in_ = images[0].shape[0]
        self.feature_names_out_ = self._names(self.n_channels_in_)
        self.scaler_ = scaler
        self.fitted_params_ = self.get_params(deep=False).copy()
        return self

    def raw_features(self, X):
        """Measure unscaled features with the fitted channel schema."""
        check_is_fitted(self, "feature_names_out_")
        if self.get_params(deep=False) != self.fitted_params_:
            raise ValueError("Parameters changed after fit; refit on reference images.")
        images = self._images(X)
        if images[0].shape[0] != self.n_channels_in_:
            raise ValueError("Channel count differs from fit.")
        return np.stack([self._features(image) for image in images])

    def transform(self, X):
        features = self.raw_features(X)
        if self.scaler_ is not None:
            return self.scaler_.transform(features)
        return features

    def get_feature_names_out(self, input_features=None):
        check_is_fitted(self, "feature_names_out_")
        if input_features is not None:
            raise ValueError("Pass image arrays, not tabular feature names.")
        return self.feature_names_out_.copy()

    def segment(self, image):
        """Return 2-D object labels, not automatic biological cell identities."""
        return self._segment(self._images([image])[0])


def read_tiff_chw(path, *, axes, series=None):
    """Read one TIFF image with an explicitly supplied YX/CYX/YXC axis order.

    File names and treatment annotations are not feature inputs. This helper
    does not guess channel semantics or flatten time/z axes. The caller must
    supply the actual stored axis order. Original numerical dtype is retained.
    """
    from tifffile import TiffFile

    if axes not in {"YX", "CYX", "YXC"}:
        raise ValueError("Supply explicit axes YX, CYX, or YXC; time/z unsupported.")
    with TiffFile(path) as tiff:
        if series is None and len(tiff.series) != 1:
            raise PixelInputError(
                "ambiguous_series", "TIFF contains multiple series; select one explicitly."
            )
        selected = 0 if series is None else series
        if type(selected) is not int or not 0 <= selected < len(tiff.series):
            raise PixelInputError("invalid_series", "TIFF series index is out of range.")
        image = tiff.series[selected].asarray()
    if image.ndim != len(axes):
        raise PixelInputError(
            "incompatible_axes", "TIFF dimensions do not match the declared axes."
        )
    if axes == "YX":
        image = image[None, ...]
    elif axes == "YXC":
        image = np.moveaxis(image, -1, 0)
    PixelMorphologyTransformer()._images([image], check_signal=False)
    return image
