from pathlib import Path

import pytest

from gerry import __main__ as cli


@pytest.fixture
def fake_pipeline(monkeypatch, valid_districts):
    calls = {}

    def fake_fetch(source, raw_dir, manifest):
        calls["fetch"] = (source.id, raw_dir, manifest)
        return Path("/fake/districts.zip")

    def fake_load(path):
        calls["load"] = path
        return calls.get("districts", valid_districts)

    monkeypatch.setattr(cli, "fetch", fake_fetch)
    monkeypatch.setattr(cli, "load_districts", fake_load)
    return calls


def test_boundaries_reports_success(fake_pipeline, tmp_path, capsys):
    assert cli.main(["boundaries", "--repo-root", str(tmp_path)]) == 0
    source_id, raw_dir, manifest = fake_pipeline["fetch"]
    assert source_id == "census-cd119-cb-2025-500k"
    assert raw_dir == tmp_path / "data" / "raw"
    assert manifest == tmp_path / "data" / "sources" / "sources.csv"
    assert fake_pipeline["load"] == Path("/fake/districts.zip")
    assert "435 districts in 50 states" in capsys.readouterr().out


def test_boundaries_fails_and_lists_problems(fake_pipeline, valid_districts, tmp_path, capsys):
    fake_pipeline["districts"] = valid_districts[valid_districts["state"] != "WY"]
    assert cli.main(["boundaries", "--repo-root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "WY: 0 districts, expected 1." in out
    assert "435 districts in 50 states" not in out


def test_default_repo_root_is_the_repository():
    assert (cli.REPO_ROOT / "CLAUDE.md").exists()
