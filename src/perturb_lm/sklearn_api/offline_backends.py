"""Family-specific inference behind LocalModelEmbedder; no asset acquisition."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ImagePreprocessing:
    """Explicit NCHW scientific-channel mapping, fixed range and normalization.

    Selected channels are resized directly to the model's declared spatial size
    with antialiased bilinear interpolation (align_corners=False). No cropping,
    channel synthesis, clipping, per-image scaling or display conversion occurs.
    All tuple parameters are immutable and become part of fitted/cache identity.
    """

    input_channels: tuple[str, ...]
    model_channels: tuple[str, str, str]
    input_range: tuple[float, float]
    mean: tuple[float, float, float]
    std: tuple[float, float, float]

    def validate(self):
        if any(
            not isinstance(value, tuple)
            for value in (
                self.input_channels,
                self.model_channels,
                self.input_range,
                self.mean,
                self.std,
            )
        ):
            raise ValueError("Preprocessing parameters must be immutable tuples")
        if (
            not self.input_channels
            or any(not isinstance(n, str) or not n.strip() for n in self.input_channels)
            or len(set(self.input_channels)) != len(self.input_channels)
            or len(self.model_channels) != 3
            or any(not isinstance(n, str) for n in self.model_channels)
            or len(set(self.model_channels)) != 3
            or not set(self.model_channels).issubset(self.input_channels)
        ):
            raise ValueError("Declare three distinct model channels from named input channels")
        for name, values, length in (
            ("input_range", self.input_range, 2),
            ("mean", self.mean, 3),
            ("std", self.std, 3),
        ):
            if len(values) != length or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)
                for v in values
            ):
                raise ValueError(f"Invalid preprocessing {name}")
        if self.input_range[0] >= self.input_range[1] or min(self.std) <= 0:
            raise ValueError("Require increasing input range and positive standard deviations")

    def validate_input(self, X):
        self.validate()
        matrix = np.asarray(X)
        if (
            matrix.dtype.kind not in "fiu"
            or matrix.ndim != 4
            or matrix.shape[1] != len(self.input_channels)
            or min(matrix.shape[2:]) < 1
            or not np.isfinite(matrix).all()
        ):
            raise ValueError("Require finite NCHW pixels matching declared input channels")
        if matrix.size and (
            matrix.min() < self.input_range[0] or matrix.max() > self.input_range[1]
        ):
            raise ValueError("Pixels outside declared input range; no implicit clipping")
        return matrix

    def tensor(self, X, spatial_shape, torch):
        matrix = self.validate_input(X)
        indices = [self.input_channels.index(name) for name in self.model_channels]
        # Copy selected decoded pixels; never mutate the caller's image buffer.
        pixels = torch.tensor(matrix[:, indices], dtype=torch.float32)
        low, high = self.input_range
        pixels = (pixels - low) / (high - low)
        pixels = torch.nn.functional.interpolate(
            pixels,
            size=tuple(spatial_shape),
            mode="bilinear",
            align_corners=False,
            antialias=True,
        )
        mean = torch.tensor(self.mean, dtype=torch.float32)[None, :, None, None]
        std = torch.tensor(self.std, dtype=torch.float32)[None, :, None, None]
        return (pixels - mean) / std


def load_family_backend(spec, local_path, device, image_preprocessing, torch, transformers):
    """Load actual local DINOv2/BERT weights; random fixtures use this same path."""
    if spec.pooling != "cls" or not spec.normalize:
        raise ValueError("DINOv2/SapBERT adapters require CLS pooling and L2 normalization")
    config = transformers.AutoConfig.from_pretrained(
        str(local_path), local_files_only=True, trust_remote_code=False
    )
    expected_type = "dinov2" if spec.name == "dinov2" else "bert"
    if config.model_type != expected_type or config.hidden_size != spec.dimension:
        raise ValueError("Local checkpoint architecture/dimension differs from AssetSpec")
    if spec.name == "dinov2":
        if (
            spec.backend != "hf_image"
            or spec.input_kind != "image"
            or len(spec.input_shape) != 3
            or spec.input_shape[0] != 3
            or min(spec.input_shape[1:]) < 1
            or config.num_channels != 3
        ):
            raise ValueError("DINOv2 requires a three-channel image model schema")
        if not isinstance(image_preprocessing, ImagePreprocessing):
            raise ValueError("DINOv2 requires explicit ImagePreprocessing")
        image_preprocessing.validate()
        model_class = transformers.Dinov2Model
        tokenizer = None
    else:
        if spec.backend != "hf_text" or spec.input_kind != "text":
            raise ValueError("SapBERT requires a text model schema")
        if (
            type(spec.max_length) is not int
            or not 2 <= spec.max_length <= config.max_position_embeddings
        ):
            raise ValueError("SapBERT max_length exceeds checkpoint positional capacity")
        model_class = transformers.BertModel
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            str(local_path), local_files_only=True, trust_remote_code=False
        )
    model, loading = model_class.from_pretrained(
        str(local_path),
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        config=config,
        output_loading_info=True,
    )
    if any(
        loading.get(key)
        for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")
    ):
        raise ValueError("Checkpoint weights do not exactly match the declared architecture")
    model = model.to(device).eval()
    model.requires_grad_(False)

    def encode(batch):
        with torch.inference_mode():
            if tokenizer is None:
                pixels = image_preprocessing.tensor(batch, spec.input_shape[1:], torch).to(device)
                hidden = model(pixel_values=pixels).last_hidden_state
            else:
                encoded = tokenizer(
                    list(batch),
                    padding=True,
                    truncation=True,
                    max_length=spec.max_length,
                    return_tensors="pt",
                )
                hidden = model(**{k: v.to(device) for k, v in encoded.items()}).last_hidden_state
            return hidden[:, 0].detach().float().cpu().numpy()

    return encode
