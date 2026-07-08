"""Unit tests for the string/text processors (positive + negative cases)."""

import re

import pytest
from autopkglib import ProcessorError
from StringFormat import StringFormat
from TextSubstitutionRegEx import TextSubstitutionRegEx
from VariableToString import VariableToString

# ---- StringFormat ---------------------------------------------------------


def test_string_format_named_kwargs():
    proc = StringFormat(
        {
            "format_string": "{name}-v{version}",
            "format_kwargs": {"name": "App", "version": "1.2"},
        }
    )
    proc.main()
    assert proc.env["formatted_string"] == "App-v1.2"


def test_string_format_value_zero_padding():
    proc = StringFormat({"format_string": "{value:0>5}", "format_value": "42"})
    proc.main()
    assert proc.env["formatted_string"] == "00042"


def test_string_format_positional_value():
    proc = StringFormat({"format_string": "[{0}]", "format_value": "x"})
    proc.main()
    assert proc.env["formatted_string"] == "[x]"


def test_string_format_missing_key_raises_processorerror():
    proc = StringFormat({"format_string": "{does_not_exist}", "format_value": "x"})
    with pytest.raises(ProcessorError):
        proc.main()


# ---- TextSubstitutionRegEx ------------------------------------------------


def test_regex_substitution_default_output_var():
    proc = TextSubstitutionRegEx(
        {
            "re_pattern": r"\d+",
            "re_substitution": "#",
            "input_string": "a1b22c333",
        }
    )
    proc.main()
    assert proc.env["result_substitution"] == "a#b#c#"


def test_regex_substitution_custom_output_var_and_groups():
    proc = TextSubstitutionRegEx(
        {
            "re_pattern": r"(\d+)\.(\d+)",
            "re_substitution": r"\2.\1",
            "input_string": "12.34",
            "result_output_var_name": "swapped",
        }
    )
    proc.main()
    assert proc.env["swapped"] == "34.12"


def test_regex_substitution_invalid_pattern_raises():
    proc = TextSubstitutionRegEx(
        {"re_pattern": "(unbalanced", "re_substitution": "x", "input_string": "abc"}
    )
    with pytest.raises(re.error):
        proc.main()


# ---- VariableToString -----------------------------------------------------


def test_variable_to_string_reads_value_into_same_name():
    proc = VariableToString({"input_variable": "count", "count": 5})
    proc.main()
    assert proc.env["count"] == "5"


def test_variable_to_string_custom_output_variable():
    proc = VariableToString(
        {"input_variable": "count", "count": 7, "output_variable": "count_str"}
    )
    proc.main()
    assert proc.env["count_str"] == "7"


def test_variable_to_string_missing_variable_becomes_none_string():
    # str(None) == "None"; the processor stringifies whatever it finds
    proc = VariableToString({"input_variable": "absent"})
    proc.main()
    assert proc.env["absent"] == "None"
