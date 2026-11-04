"""Download raw data sources, cache them, and record them in the sources manifest.

Each source is downloaded once into `data/raw/<source id>/` (gitignored) and recorded
in `data/sources/sources.csv` (committed) with its URL, publisher, license, download
date and SHA-256 checksum. Later runs reuse the cached file. If a cached file or a
fresh download no longer matches the recorded checksum, the source has changed and
fetching fails, so the pipeline never silently runs on different data.
"""

import csv
import hashlib
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx

MANIFEST_FIELDS = ["id", "url", "publisher", "license", "description", "downloaded", "sha256"]


@dataclass(frozen=True)
class Source:
    """A raw data file and where it comes from."""

    id: str
    url: str
    publisher: str
    license: str
    description: str
    # Local file name, for URLs that don't end in one (API download links).
    filename: str | None = None


class SourceChangedError(Exception):
    """A source no longer matches the checksum recorded for it."""


CENSUS_CD119 = Source(
    id="census-cd119-cb-2025-500k",
    url="https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_cd119_500k.zip",
    publisher="U.S. Census Bureau",
    license="Public domain (U.S. Government work)",
    description=(
        "Cartographic boundary file, 119th Congress districts, 2025 edition, 1:500,000, "
        "clipped to the shoreline"
    ),
)


CENSUS_STATES = Source(
    id="census-states-cb-2025-500k",
    url="https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_500k.zip",
    publisher="U.S. Census Bureau",
    license="Public domain (U.S. Government work)",
    description=(
        "Cartographic boundary file, states, 2025 edition, 1:500,000, clipped to the "
        "shoreline. Used to clip replacement district maps to land."
    ),
)


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    """Read the sources manifest, keyed by source ID. A missing file reads as empty."""
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def _write_manifest(path: Path, entries: dict[str, dict[str, str]]) -> None:
    """Write the manifest sorted by source ID, so diffs stay small."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(entries[key] for key in sorted(entries))


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, folder: Path, client: httpx.Client) -> Path:
    """Stream url into a temporary file in folder and return its path.

    Raises:
        httpx.HTTPStatusError: on a non-2xx response. No file is left behind.
    """
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, suffix=".part", delete=False) as tmp:
        partial = Path(tmp.name)
        try:
            with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    tmp.write(chunk)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
    return partial


def fetch(
    source: Source,
    raw_dir: Path,
    manifest: Path,
    client: httpx.Client | None = None,
    today: date | None = None,
) -> Path:
    """Return the local path of a source, downloading it if needed.

    Raises:
        SourceChangedError: if the cached file or a fresh download doesn't match the
            checksum recorded in the manifest.
        httpx.HTTPStatusError: if the download fails.
    """
    name = source.filename or PurePosixPath(urlparse(source.url).path).name
    target = raw_dir / source.id / name
    entries = read_manifest(manifest)
    recorded = entries.get(source.id, {}).get("sha256")
    if target.exists():
        if recorded and _sha256(target) != recorded:
            raise SourceChangedError(f"{target} no longer matches its recorded checksum.")
        return target
    with client or httpx.Client(timeout=60) as http:
        partial = _download(source.url, target.parent, http)
    actual = _sha256(partial)
    if recorded and actual != recorded:
        partial.unlink()
        raise SourceChangedError(
            f"{source.url} has changed since it was recorded (sha256 {actual}, "
            f"recorded {recorded}). Check the new edition, then update the manifest."
        )
    partial.replace(target)
    if not recorded:
        downloaded = (today or date.today()).isoformat()
        details = {k: v for k, v in asdict(source).items() if k in MANIFEST_FIELDS}
        entries[source.id] = {**details, "downloaded": downloaded, "sha256": actual}
        _write_manifest(manifest, entries)
    return target
