"""Top-level Perturb LM CLI."""

from __future__ import annotations

import typer

from perturb_lm import __version__
from perturb_lm.cli.images import app as images_app

app = typer.Typer(help="Perturb LM command line tools.")
app.add_typer(images_app, name="images")


@app.command()
def version() -> None:
    """Print the installed Perturb LM version."""

    typer.echo(__version__)


if __name__ == "__main__":
    app()
