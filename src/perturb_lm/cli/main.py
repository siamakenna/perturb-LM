"""Top-level Perturb LM CLI."""

from __future__ import annotations

import typer

from perturb_lm import __version__

app = typer.Typer(help="Perturb LM command line tools.")


@app.command()
def version() -> None:
    """Print the installed Perturb LM version."""

    typer.echo(__version__)


if __name__ == "__main__":
    app()
