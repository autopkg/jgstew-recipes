"""Unit tests for the dictionary/template-dictionary processors."""

# pre-commit-skip: processor-conventions
import pytest
from autopkglib import ProcessorError
from DictionaryKeyRead import DictionaryKeyRead
from TemplateDictionaryAppend import TemplateDictionaryAppend
from TemplateDictionaryReadKey import TemplateDictionaryReadKey
from TemplateDictionaryRemove import TemplateDictionaryRemove

# ---- DictionaryKeyRead ----------------------------------------------------
# input_dictionary is the NAME of an env var that holds the dict.


def test_dictionary_key_read_stringifies_by_default():
    proc = DictionaryKeyRead(
        {
            "mydict": {"version": 5},
            "input_dictionary": "mydict",
            "dictionary_key": "version",
            "output_variable": "out",
        }
    )
    proc.main()
    assert proc.env["out"] == "5"  # stringified


def test_dictionary_key_read_output_string_false_keeps_type():
    proc = DictionaryKeyRead(
        {
            "mydict": {"version": 5},
            "input_dictionary": "mydict",
            "dictionary_key": "version",
            "output_variable": "out",
            "output_string": False,
        }
    )
    proc.main()
    assert proc.env["out"] == 5  # int preserved


def test_dictionary_key_read_missing_key_raises():
    proc = DictionaryKeyRead(
        {
            "mydict": {"version": 5},
            "input_dictionary": "mydict",
            "dictionary_key": "absent",
            "output_variable": "out",
        }
    )
    with pytest.raises(ProcessorError):
        proc.main()


def test_dictionary_key_read_missing_dictionary_raises():
    proc = DictionaryKeyRead(
        {
            "input_dictionary": "nope",
            "dictionary_key": "version",
            "output_variable": "out",
        }
    )
    with pytest.raises(ProcessorError):
        proc.main()


# ---- TemplateDictionaryReadKey --------------------------------------------


def test_template_dictionary_read_key():
    proc = TemplateDictionaryReadKey(
        {"template_dictionary": {"version": "1.2"}, "dictionary_key": "version"}
    )
    proc.main()
    assert proc.env["dictionary_value"] == "1.2"


def test_template_dictionary_read_key_custom_value_name():
    proc = TemplateDictionaryReadKey(
        {
            "template_dictionary": {"version": "1.2"},
            "dictionary_key": "version",
            "dictionary_value_name": "app_version",
        }
    )
    proc.main()
    assert proc.env["app_version"] == "1.2"


def test_template_dictionary_read_key_missing_raises_keyerror():
    proc = TemplateDictionaryReadKey(
        {"template_dictionary": {"version": "1.2"}, "dictionary_key": "absent"}
    )
    with pytest.raises(KeyError):
        proc.main()


# ---- TemplateDictionaryAppend ---------------------------------------------


def test_template_dictionary_append_adds_key_and_stringifies_value():
    proc = TemplateDictionaryAppend(
        {
            "template_dictionary": {"a": "1"},
            "append_key": "b",
            "append_value": 2,
        }
    )
    proc.main()
    assert proc.env["template_dictionary"] == {"a": "1", "b": "2"}
    assert proc.env["dictionary_appended"] == {"a": "1", "b": "2"}


def test_template_dictionary_append_creates_dict_when_absent():
    proc = TemplateDictionaryAppend({"append_key": "x", "append_value": "y"})
    proc.main()
    assert proc.env["template_dictionary"] == {"x": "y"}


# ---- TemplateDictionaryRemove ---------------------------------------------


def test_template_dictionary_remove_key():
    proc = TemplateDictionaryRemove(
        {"template_dictionary": {"a": "1", "b": "2"}, "remove_key": "a"}
    )
    proc.main()
    assert proc.env["template_dictionary"] == {"b": "2"}
    assert proc.env["dictionary_reduced"] == {"b": "2"}


def test_template_dictionary_remove_missing_key_is_noop():
    proc = TemplateDictionaryRemove(
        {"template_dictionary": {"a": "1"}, "remove_key": "absent"}
    )
    proc.main()  # must not raise
    assert proc.env["dictionary_reduced"] == {"a": "1"}
