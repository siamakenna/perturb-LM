"""TIFF analysis commands on the existing Typer package CLI."""

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Pixel-only TIFF analysis, reference fitting, and image search.")
Paths = Annotated[
    list[Path], typer.Argument(help="Explicit local TIFF paths; order defines default row IDs.")
]
Axes = Annotated[str, typer.Option(help="Required stored axes: YX, CYX, or YXC.")]
Channels = Annotated[
    str, typer.Option(help="Required comma-separated channel names in stored order.")
]
Output = Annotated[Path, typer.Option("--out", help="New output directory; never overwrite.")]
Ids = Annotated[
    list[str] | None,
    typer.Option("--image-id", help="Repeat once per path; otherwise ordinal IDs."),
]


def _run(paths, out, axes, channels, **kwargs):
    try:
        from perturb_lm.images.pixel_workflow import run_images
    except ImportError as error:
        typer.echo(f"Install the pixel extra: pip install 'perturb-lm[pixel]' ({error})", err=True)
        raise typer.Exit(2) from error
    try:
        result = run_images(
            paths,
            output=out,
            axes=axes,
            channels=[name.strip() for name in channels.split(",")],
            **kwargs,
        )
    except (ValueError, OSError) as error:
        typer.echo(f"Image workflow failed: {error}", err=True)
        raise typer.Exit(2) from error
    typer.echo(
        f"{result['n_accepted']} accepted; {result['n_excluded']} excluded. "
        f"Report: {out / 'report.html'}"
    )
    if result["n_accepted"] == 0:
        raise typer.Exit(2)
    if result["n_excluded"]:
        raise typer.Exit(1)


@app.command()
def analyze(
    paths: Paths,
    axes: Axes,
    channels: Channels,
    out: Output,
    image_id: Ids = None,
    state: Annotated[
        Path | None, typer.Option(help="Reference state.json; never refit on analysis images.")
    ] = None,
    segmentation_channel: int = 0,
    min_object_area: int = 8,
    smooth_sigma: float = 1.0,
    min_peak_distance: int = 4,
    series: int | None = None,
):
    """Export raw measurements/masks/report; scaled features require --state."""
    if state is not None:
        # Avoid silently ignoring caller overrides when state supplies the parameters.
        if (segmentation_channel, min_object_area, smooth_sigma, min_peak_distance) != (
            0,
            8,
            1.0,
            4,
        ):
            raise typer.BadParameter(
                "With --state, segmentation parameters come from reference state."
            )
    _run(
        paths,
        out,
        axes,
        channels,
        mode="analyze",
        image_ids=image_id,
        state=state,
        segmentation_channel=segmentation_channel,
        min_object_area=min_object_area,
        smooth_sigma=smooth_sigma,
        min_peak_distance=min_peak_distance,
        series=series,
    )


@app.command()
def fit(
    paths: Paths,
    axes: Axes,
    channels: Channels,
    out: Output,
    image_id: Ids = None,
    segmentation_channel: int = 0,
    min_object_area: int = 8,
    smooth_sigma: float = 1.0,
    min_peak_distance: int = 4,
    series: int | None = None,
):
    """Fit preprocessing on these reference images only and persist an image index."""
    _run(
        paths,
        out,
        axes,
        channels,
        mode="fit",
        image_ids=image_id,
        segmentation_channel=segmentation_channel,
        min_object_area=min_object_area,
        smooth_sigma=smooth_sigma,
        min_peak_distance=min_peak_distance,
        series=series,
    )


@app.command()
def search(
    paths: Paths,
    axes: Axes,
    channels: Channels,
    out: Output,
    reference: Annotated[Path, typer.Option(help="Directory produced by images fit.")],
    image_id: Ids = None,
    top_k: int = 5,
    series: int | None = None,
):
    """Apply saved reference preprocessing and find nearest reference image rows."""
    _run(
        paths,
        out,
        axes,
        channels,
        mode="search",
        image_ids=image_id,
        reference=reference,
        top_k=top_k,
        series=series,
    )
