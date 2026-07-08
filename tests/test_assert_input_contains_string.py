"""Unit tests for AssertInputContainsString (positive + negative cases)."""

import pytest
from AssertInputContainsString import AssertInputContainsString


def test_assert_found_sets_result():
    proc = AssertInputContainsString({"input_string": "1_2_3", "assert_string": "_"})
    proc.main()
    assert proc.env["assert_result"] == "found!"


def test_assert_found_substring():
    proc = AssertInputContainsString(
        {"input_string": "com.github.jgstew.test.Foo", "assert_string": "jgstew"}
    )
    proc.main()
    assert proc.env["assert_result"] == "found!"


def test_assert_not_found_raises_by_default():
    proc = AssertInputContainsString({"input_string": "abc", "assert_string": "xyz"})
    with pytest.raises(AssertionError):
        proc.main()


def test_assert_not_found_without_raise_records_error():
    proc = AssertInputContainsString(
        {"input_string": "abc", "assert_string": "xyz", "raise_error": False}
    )
    proc.main()  # must not raise
    assert proc.env["assert_result"].startswith("ERROR")


def test_assert_coerces_non_string_inputs():
    # input_string/assert_string are str()-coerced before the containment check
    proc = AssertInputContainsString({"input_string": 12345, "assert_string": 234})
    proc.main()
    assert proc.env["assert_result"] == "found!"
