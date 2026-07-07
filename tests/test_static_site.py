from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


SITE_ROOT = Path("site")
FORBIDDEN_PUBLIC_STRINGS = [
    "jump_pilot_real_baseline",
    "BR00116991",
    "BR00116992",
    "linkedin_assets",
    ".parquet",
    ".npy",
    ".npz",
    ".pkl",
    ".pt",
    ".safetensors",
]


class _HtmlSmokeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.has_title = False
        self.has_description = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        payload = dict(attrs)
        if tag == "a" and payload.get("href"):
            self.links.append(str(payload["href"]))
        if tag == "title":
            self.has_title = True
        if tag == "meta" and payload.get("name") == "description":
            self.has_description = True


def test_static_site_has_required_public_files() -> None:
    for relative_path in [
        "index.html",
        "404.html",
        "styles.css",
        "robots.txt",
        "sitemap.xml",
        ".nojekyll",
    ]:
        assert (SITE_ROOT / relative_path).exists()


def test_static_site_index_is_parseable_and_has_core_copy() -> None:
    html = (SITE_ROOT / "index.html").read_text()
    parser = _HtmlSmokeParser()
    parser.feed(html)

    assert parser.has_title
    assert parser.has_description
    assert "Identifier-stripped TF-IDF" in html
    assert "This is not yet biological image understanding" in html
    assert "https://github.com/siamakenna/perturb-LM" in parser.links


def test_static_site_does_not_publish_local_artifacts() -> None:
    public_files = [
        path for path in SITE_ROOT.rglob("*") if path.is_file() and path.name != ".nojekyll"
    ]
    for path in public_files:
        text = path.read_text(errors="ignore")
        for forbidden in FORBIDDEN_PUBLIC_STRINGS:
            assert forbidden not in text, f"{forbidden} leaked in {path}"
