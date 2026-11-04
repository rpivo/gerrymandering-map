import hashlib
from datetime import date

import httpx
import pytest

from gerry.fetch import Source, SourceChangedError, fetch, read_manifest

SOURCE = Source(
    id="test-districts",
    url="https://example.test/files/districts.zip",
    publisher="Test Bureau",
    license="Public domain",
    description="Test file",
)
BODY = b"district shapes"
SHA = hashlib.sha256(BODY).hexdigest()
TODAY = date(2026, 11, 4)


class FakeServer:
    """Serves one body for every request and counts requests."""

    def __init__(self, body: bytes = BODY, status: int = 200):
        self.body, self.status, self.requests = body, status, 0

    def client(self) -> httpx.Client:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests += 1
            return httpx.Response(self.status, content=self.body)

        return httpx.Client(transport=httpx.MockTransport(handle))


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "raw", tmp_path / "sources.csv"


def run(paths, server: FakeServer):
    raw_dir, manifest = paths
    return fetch(SOURCE, raw_dir, manifest, client=server.client(), today=TODAY)


def test_downloads_and_records_the_source(paths):
    path = run(paths, FakeServer())
    assert path == paths[0] / "test-districts" / "districts.zip"
    assert path.read_bytes() == BODY
    entry = read_manifest(paths[1])["test-districts"]
    assert entry == {
        "id": "test-districts",
        "url": SOURCE.url,
        "publisher": "Test Bureau",
        "license": "Public domain",
        "description": "Test file",
        "downloaded": "2026-11-04",
        "sha256": SHA,
    }


def test_cached_file_is_reused_without_downloading(paths):
    run(paths, FakeServer())
    server = FakeServer()
    assert run(paths, server).read_bytes() == BODY
    assert server.requests == 0


def test_cached_file_that_no_longer_matches_its_checksum_fails(paths):
    path = run(paths, FakeServer())
    path.write_bytes(b"tampered")
    with pytest.raises(SourceChangedError, match="checksum"):
        run(paths, FakeServer())


def test_redownload_that_differs_from_the_recorded_checksum_fails(paths):
    path = run(paths, FakeServer())
    path.unlink()
    with pytest.raises(SourceChangedError, match="changed"):
        run(paths, FakeServer(body=b"a new edition"))
    assert not path.exists()
    assert read_manifest(paths[1])["test-districts"]["sha256"] == SHA


def test_redownload_with_the_same_content_succeeds(paths):
    path = run(paths, FakeServer())
    path.unlink()
    assert run(paths, FakeServer()).read_bytes() == BODY


def test_http_error_leaves_no_file_and_no_manifest_entry(paths):
    with pytest.raises(httpx.HTTPStatusError):
        run(paths, FakeServer(status=404))
    assert list((paths[0] / "test-districts").iterdir()) == []
    assert read_manifest(paths[1]) == {}


def test_manifest_keeps_other_sources_sorted_by_id(paths):
    raw_dir, manifest = paths
    manifest.write_text(
        "id,url,publisher,license,description,downloaded,sha256\n"
        "zz-other,https://x.test/z,X,CC0,Other,2026-01-01,abc\n"
    )
    run(paths, FakeServer())
    assert list(read_manifest(manifest)) == ["test-districts", "zz-other"]
    assert read_manifest(manifest)["zz-other"]["sha256"] == "abc"
