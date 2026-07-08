"""Unit tests for the version-handling processors (positive + negative cases)."""

import pytest
from autopkglib import ProcessorError
from VersionCompare import VersionCompare, compare_versions
from VersionGetMajorMinor import VersionGetMajorMinor, get_version_major_minor
from VersionMaximumArray import VersionMaximumArray
from VersionSort import VersionSort

# ---- VersionCompare -------------------------------------------------------


@pytest.mark.parametrize(
    "v1, v2, expected_int",
    [
        ("1.2.3", "1.2.10", -1),  # numeric, not lexical (10 > 3)
        ("2.0", "1.9.9", 1),
        ("1.0.0", "1.0.0", 0),
    ],
)
def test_compare_versions(v1, v2, expected_int):
    assert compare_versions(v1, v2) == expected_int


def test_version_compare_newer():
    proc = VersionCompare({"version1": "2.0", "version2": "1.5"})
    proc.main()
    assert proc.env["version_comparison_result"] == "newer"
    assert proc.env["version_comparison_int"] == 1
    assert proc.env["version_newest"] == "2.0"


def test_version_compare_older():
    proc = VersionCompare({"version1": "1.0", "version2": "1.0.1"})
    proc.main()
    assert proc.env["version_comparison_result"] == "older"
    assert proc.env["version_newest"] == "1.0.1"


def test_version_compare_equal_prefers_version2_as_newest():
    proc = VersionCompare({"version1": "1.0", "version2": "1.0"})
    proc.main()
    assert proc.env["version_comparison_result"] == "equal"
    assert proc.env["version_comparison_int"] == 0
    assert proc.env["version_newest"] == "1.0"


# ---- VersionGetMajorMinor -------------------------------------------------


def test_get_version_major_minor_default_separator():
    assert get_version_major_minor("1.2.3.4") == "1.2"


def test_get_version_major_minor_custom_separator():
    assert get_version_major_minor("11.0.6.137", separator_string="") == "110"


def test_version_get_major_minor_main_uses_version_maximum_default():
    proc = VersionGetMajorMinor({"version_maximum": "3.4.5"})
    proc.main()
    assert proc.env["version_major_minor"] == "3.4"


def test_version_get_major_minor_main_explicit_and_separator():
    proc = VersionGetMajorMinor({"version_string": "7.8.9", "separator_string": "-"})
    proc.main()
    assert proc.env["version_major_minor"] == "7-8"


# ---- VersionMaximumArray --------------------------------------------------


def test_version_maximum_array_picks_largest():
    proc = VersionMaximumArray({"version_array": ["1.2.9", "1.2.10", "1.2.3"]})
    proc.main()
    assert proc.env["version_maximum"] == "1.2.10"


def test_version_maximum_array_filtered_by_major_minor():
    proc = VersionMaximumArray(
        {
            "version_array": ["1.2.9", "1.3.0", "1.2.10"],
            "version_major_minor_match": "1.2",
        }
    )
    proc.main()
    assert proc.env["version_maximum"] == "1.2.10"


def test_version_maximum_array_defaults_to_match():
    proc = VersionMaximumArray({"match": ["9.0", "10.0", "2.0"]})
    proc.main()
    assert proc.env["version_maximum"] == "10.0"


def test_version_maximum_array_empty_after_filter_raises():
    proc = VersionMaximumArray(
        {"version_array": ["1.2.9"], "version_major_minor_match": "9.9"}
    )
    with pytest.raises(ValueError):  # max() of empty sequence
        proc.main()


# ---- VersionSort ----------------------------------------------------------


def test_version_sort_ascending():
    proc = VersionSort({"version_array": ["1.2.10", "1.2.9", "1.10.0"]})
    proc.main()
    assert proc.env["version_array_sorted"] == ["1.2.9", "1.2.10", "1.10.0"]
    assert proc.env["version_minimum"] == "1.2.9"
    assert proc.env["version_maximum"] == "1.10.0"


def test_version_sort_descending():
    proc = VersionSort(
        {"version_array": ["1.2.10", "1.2.9", "1.10.0"], "sort_descending": True}
    )
    proc.main()
    assert proc.env["version_array_sorted"] == ["1.10.0", "1.2.10", "1.2.9"]


def test_version_sort_empty_raises():
    proc = VersionSort({"version_array": []})
    with pytest.raises(ProcessorError):
        proc.main()


def test_version_sort_missing_raises():
    proc = VersionSort({})
    with pytest.raises(ProcessorError):
        proc.main()
