"""Unit tests for URLDownloaderPython's parent-cache reuse helpers.

These cover the self-contained cache introspection / copy-on-reuse logic without
any network I/O.
"""

import json
import os
import textwrap

import pytest
from URLDownloaderPython import URLDownloaderPython


def _make_recipe(path, identifier):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(textwrap.dedent(f"""\
                Description: test
                Identifier: {identifier}
                Input:
                  NAME: Test
                Process: []
                """))


def _make_cached_download(downloads_dir, filename, content=b"payload"):
    os.makedirs(downloads_dir, exist_ok=True)
    payload = os.path.join(downloads_dir, filename)
    with open(payload, "wb") as handle:
        handle.write(content)
    with open(payload + ".info.json", "w", encoding="utf-8") as handle:
        json.dump({"file_name": filename, "http_headers": {"ETag": "x"}}, handle)
    return payload


# ---- get_parent_cache_dirs ------------------------------------------------


def test_get_parent_cache_dirs(tmp_path):
    recipe = tmp_path / "Parent.download.recipe.yaml"
    _make_recipe(recipe, "com.test.parent")
    cache = tmp_path / "cache"
    proc = URLDownloaderPython(
        {"PARENT_RECIPES": [str(recipe)], "CACHE_DIR": str(cache)}
    )
    assert proc.get_parent_cache_dirs() == [os.path.join(str(cache), "com.test.parent")]


def test_get_parent_cache_dirs_no_parents(tmp_path):
    proc = URLDownloaderPython({"PARENT_RECIPES": [], "CACHE_DIR": str(tmp_path)})
    assert proc.get_parent_cache_dirs() == []


# ---- find_newest_parent_download ------------------------------------------


@pytest.fixture
def proc_with_two_parents(tmp_path):
    """A processor whose two parents each have a downloads dir under CACHE_DIR."""
    cache = tmp_path / "cache"
    p1 = tmp_path / "P1.download.recipe.yaml"
    p2 = tmp_path / "P2.download.recipe.yaml"
    _make_recipe(p1, "com.test.p1")
    _make_recipe(p2, "com.test.p2")
    proc = URLDownloaderPython(
        {"PARENT_RECIPES": [str(p1), str(p2)], "CACHE_DIR": str(cache)}
    )
    p1_dl = os.path.join(str(cache), "com.test.p1", "downloads")
    p2_dl = os.path.join(str(cache), "com.test.p2", "downloads")
    return proc, p1_dl, p2_dl


def test_find_newest_returns_none_when_absent(proc_with_two_parents):
    proc, _p1_dl, _p2_dl = proc_with_two_parents
    assert proc.find_newest_parent_download("thing.zip") is None


def test_find_newest_picks_newest_by_mtime(proc_with_two_parents):
    proc, p1_dl, p2_dl = proc_with_two_parents
    older = _make_cached_download(p1_dl, "thing.zip")
    newer = _make_cached_download(p2_dl, "thing.zip")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))
    assert proc.find_newest_parent_download("thing.zip") == newer


def test_find_newest_skips_payload_without_info_sidecar(proc_with_two_parents):
    proc, p1_dl, _p2_dl = proc_with_two_parents
    os.makedirs(p1_dl, exist_ok=True)
    # payload present but no .info.json -> not a candidate
    with open(os.path.join(p1_dl, "thing.zip"), "wb") as handle:
        handle.write(b"payload")
    assert proc.find_newest_parent_download("thing.zip") is None


def test_find_newest_skips_zero_byte_payload(proc_with_two_parents):
    proc, p1_dl, _p2_dl = proc_with_two_parents
    _make_cached_download(p1_dl, "thing.zip", content=b"")
    assert proc.find_newest_parent_download("thing.zip") is None


# ---- reuse_newest_parent_download (copy on reuse) -------------------------


def test_reuse_copies_when_current_missing(proc_with_two_parents, tmp_path):
    proc, p1_dl, _p2_dl = proc_with_two_parents
    _make_cached_download(p1_dl, "thing.zip", content=b"PARENT")
    current = tmp_path / "child" / "downloads" / "thing.zip"
    os.makedirs(current.parent, exist_ok=True)
    proc.env["pathname"] = str(current)

    proc.reuse_newest_parent_download("thing.zip")

    assert current.read_bytes() == b"PARENT"
    assert (current.parent / "thing.zip.info.json").is_file()


def test_reuse_is_idempotent(proc_with_two_parents, tmp_path):
    proc, p1_dl, _p2_dl = proc_with_two_parents
    _make_cached_download(p1_dl, "thing.zip", content=b"PARENT")
    current = tmp_path / "child" / "downloads" / "thing.zip"
    os.makedirs(current.parent, exist_ok=True)
    proc.env["pathname"] = str(current)

    proc.reuse_newest_parent_download("thing.zip")
    mtime_after_first = current.stat().st_mtime
    proc.reuse_newest_parent_download("thing.zip")
    assert current.stat().st_mtime == mtime_after_first


def test_reuse_does_not_overwrite_newer_current(proc_with_two_parents, tmp_path):
    proc, p1_dl, _p2_dl = proc_with_two_parents
    source = _make_cached_download(p1_dl, "thing.zip", content=b"PARENT")
    os.utime(source, (1000, 1000))
    current = tmp_path / "child" / "downloads" / "thing.zip"
    os.makedirs(current.parent, exist_ok=True)
    current.write_bytes(b"CURRENT-NEWER")
    os.utime(current, (5000, 5000))
    proc.env["pathname"] = str(current)

    proc.reuse_newest_parent_download("thing.zip")
    assert current.read_bytes() == b"CURRENT-NEWER"  # untouched


def test_reuse_noop_when_no_parent_copy(proc_with_two_parents, tmp_path):
    proc, _p1_dl, _p2_dl = proc_with_two_parents
    current = tmp_path / "child" / "downloads" / "absent.zip"
    os.makedirs(current.parent, exist_ok=True)
    proc.env["pathname"] = str(current)
    proc.reuse_newest_parent_download("absent.zip")
    assert not current.exists()
