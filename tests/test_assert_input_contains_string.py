"""Unit tests for AssertInputContainsString (positive + negative cases)."""

import pytest
from AssertInputContainsString import AssertInputContainsString
from autopkglib import ProcessorError


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


# ---- via Processor.process() ----------------------------------------------
# process() is AutoPkg's real entry point: it applies input_variables defaults
# and enforces `required` inputs, then calls main(). These tests drive the
# processor the way the AutoPkg engine does, exercising that wrapping around
# main() rather than calling main() directly.


def test_process_returns_env_on_success():
    proc = AssertInputContainsString({"input_string": "1_2_3", "assert_string": "_"})
    result = proc.process()
    assert result is proc.env
    assert result["assert_result"] == "found!"


def test_process_applies_raise_error_default_and_raises_when_not_found():
    # raise_error is not supplied; process() must apply its default (True) from
    # input_variables, so a not-found assertion raises.
    proc = AssertInputContainsString({"input_string": "abc", "assert_string": "xyz"})
    assert "raise_error" not in proc.env  # default not applied yet
    with pytest.raises(AssertionError):
        proc.process()
    assert proc.env["raise_error"] is True  # process() applied the default


def test_process_respects_raise_error_false():
    proc = AssertInputContainsString(
        {"input_string": "abc", "assert_string": "xyz", "raise_error": False}
    )
    result = proc.process()  # must not raise
    assert result["assert_result"].startswith("ERROR")


def test_process_missing_required_input_string_raises():
    proc = AssertInputContainsString({"assert_string": "x"})
    with pytest.raises(ProcessorError):
        proc.process()


def test_process_missing_required_assert_string_raises():
    proc = AssertInputContainsString({"input_string": "abc"})
    with pytest.raises(ProcessorError):
        proc.process()
