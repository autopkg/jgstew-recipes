"""Unit tests for FolderListFiles (positive + negative cases)."""

# pre-commit-skip: processor-conventions
import os

import pytest
from autopkglib import ProcessorError
from FolderListFiles import FolderListFiles


@pytest.fixture
def sample_folder(tmp_path):
    """A folder with two files and a subfolder containing one file."""
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.pkg").write_text("b", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("c", encoding="utf-8")
    return tmp_path


def _run(folder, **env):
    env["folder_path"] = str(folder)
    proc = FolderListFiles(env)
    proc.main()
    return proc.env


def test_lists_files_non_recursive(sample_folder):
    env = _run(sample_folder)
    assert env["folder_file_names"] == ["a.txt", "b.pkg"]  # files only, sorted
    assert env["folder_file_count"] == 2
    # full paths, and the string output is the newline-joined paths
    assert env["folder_file_list"] == [
        os.path.join(str(sample_folder), "a.txt"),
        os.path.join(str(sample_folder), "b.pkg"),
    ]
    assert env["folder_file_list_string"] == "\n".join(env["folder_file_list"])


def test_include_dirs(sample_folder):
    env = _run(sample_folder, include_dirs=True)
    assert env["folder_file_names"] == ["a.txt", "b.pkg", "sub"]


def test_pattern_filter(sample_folder):
    env = _run(sample_folder, pattern="*.pkg")
    assert env["folder_file_names"] == ["b.pkg"]
    assert env["folder_file_count"] == 1


def test_pattern_matches_nothing(sample_folder):
    env = _run(sample_folder, pattern="*.dmg")
    assert env["folder_file_names"] == []
    assert env["folder_file_count"] == 0
    assert env["folder_file_list_string"] == ""


def test_recursive_walks_subfolders(sample_folder):
    env = _run(sample_folder, recursive=True)
    assert sorted(env["folder_file_names"]) == ["a.txt", "b.pkg", "c.txt"]
    assert env["folder_file_count"] == 3


def test_sort_results_false_returns_same_set(sample_folder):
    env = _run(sample_folder, sort_results=False)
    assert set(env["folder_file_names"]) == {"a.txt", "b.pkg"}


def test_empty_folder(tmp_path):
    env = _run(tmp_path)
    assert env["folder_file_list"] == []
    assert env["folder_file_names"] == []
    assert env["folder_file_count"] == 0
    assert env["folder_file_list_string"] == ""


def test_missing_folder_raises(tmp_path):
    proc = FolderListFiles({"folder_path": str(tmp_path / "does_not_exist")})
    with pytest.raises(ProcessorError):
        proc.main()


def test_folder_path_is_a_file_raises(sample_folder):
    proc = FolderListFiles({"folder_path": str(sample_folder / "a.txt")})
    with pytest.raises(ProcessorError):
        proc.main()


def test_missing_folder_path_raises():
    proc = FolderListFiles({})
    with pytest.raises(ProcessorError):
        proc.main()
