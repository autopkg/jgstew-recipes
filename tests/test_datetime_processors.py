"""Unit tests for DateTimeFromString and DateTimeNow."""

# pre-commit-skip: processor-conventions
import pytest
from autopkglib import ProcessorError
from DateTimeFromString import DateTimeFromString
from DateTimeNow import DateTimeNow

# ---- DateTimeFromString ---------------------------------------------------


def test_datetime_from_string_reformats():
    proc = DateTimeFromString(
        {
            "datetime_string": "2021-08-03",
            "datetime_strptime": "%Y-%m-%d",
            "datetime_strftime": "%m/%d/%Y",
        }
    )
    proc.main()
    assert proc.env["datetime_parsed"] == "08/03/2021"


def test_datetime_from_string_custom_output_name():
    proc = DateTimeFromString(
        {
            "datetime_string": "Wed, 09 Mar 2022 18:26:34 GMT",
            "datetime_strptime": "%a, %d %b %Y %H:%M:%S %Z",
            "datetime_strftime": "%Y-%m-%d",
            "datetime_parsed_name": "SourceReleaseDate",
        }
    )
    proc.main()
    assert proc.env["SourceReleaseDate"] == "2022-03-09"
    assert proc.env["datetime_parsed"] == "2022-03-09"


def test_datetime_from_string_bad_input_raises_valueerror():
    proc = DateTimeFromString(
        {
            "datetime_string": "not-a-date",
            "datetime_strptime": "%Y-%m-%d",
            "datetime_strftime": "%Y",
        }
    )
    with pytest.raises(ValueError):
        proc.main()


# ---- DateTimeNow ----------------------------------------------------------


def test_datetime_now_default_outputs_types():
    proc = DateTimeNow({})
    proc.main()
    assert isinstance(proc.env["datetime_now"], str)
    assert "T" in proc.env["datetime_now_iso"]
    assert isinstance(proc.env["datetime_now_epoch"], float)


def test_datetime_now_utc_iso_has_utc_offset():
    proc = DateTimeNow({"datetime_use_utc": True})
    proc.main()
    assert proc.env["datetime_now_iso"].endswith("+00:00")


def test_datetime_now_offset_shifts_epoch():
    base = DateTimeNow({"datetime_offset_hours": 0, "datetime_use_utc": True})
    base.main()
    plus2 = DateTimeNow({"datetime_offset_hours": 2, "datetime_use_utc": True})
    plus2.main()
    # +2h == +7200s; allow a few seconds of wall-clock drift between the calls
    assert (
        abs((plus2.env["datetime_now_epoch"] - base.env["datetime_now_epoch"]) - 7200)
        < 5
    )


def test_datetime_now_custom_format():
    proc = DateTimeNow({"datetime_use_utc": True, "datetime_strftime": "YEAR=%Y"})
    proc.main()
    assert proc.env["datetime_now"].startswith("YEAR=20")


def test_datetime_now_string_offset_is_coerced():
    proc = DateTimeNow({"datetime_offset_hours": "-3"})
    proc.main()  # must not raise
    assert isinstance(proc.env["datetime_now_epoch"], float)


def test_datetime_now_bad_offset_raises_processorerror():
    proc = DateTimeNow({"datetime_offset_hours": "not-a-number"})
    with pytest.raises(ProcessorError):
        proc.main()
