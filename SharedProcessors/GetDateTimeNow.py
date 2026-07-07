#!/usr/local/autopkg/python
#
# James Stewart @JGStew - 2026
#
# Link:
# - https://github.com/jgstew/jgstew-recipes/blob/main/SharedProcessors/GetDateTimeNow.py
#
"""See docstring for GetDateTimeNow class

to run this directly from bash, use:

```
PYTHONPATH="../autopkg/Code:SharedProcessors" ./.venv/bin/python <<EOF
from GetDateTimeNow import GetDateTimeNow
p = GetDateTimeNow({"datetime_offset_hours": -5})
p.main()
print(p.env)
EOF
```

"""

import datetime

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)

__all__ = ["GetDateTimeNow"]


class GetDateTimeNow(Processor):  # pylint: disable=invalid-name
    """Gets the current date and time, with an optional offset in hours (positive or negative)."""

    description = __doc__
    input_variables = {
        "datetime_offset_hours": {
            "required": False,
            "default": 0,
            "description": (
                "Number of hours to offset from now. May be positive or "
                "negative and may be fractional (e.g. -5, 1.5). Default: 0"
            ),
        },
        "datetime_use_utc": {
            "required": False,
            "default": False,
            "description": (
                "If True, base the result on UTC; otherwise use the local "
                "system time zone. Default: False (local time)"
            ),
        },
        "datetime_strftime": {
            "required": False,
            "default": "%Y-%m-%d %H:%M:%S",
            "description": (
                "strftime format used to build 'datetime_now'. "
                "Default: '%Y-%m-%d %H:%M:%S'"
            ),
        },
    }
    output_variables = {
        "datetime_now": {
            "description": "The offset date/time formatted with 'datetime_strftime'.",
        },
        "datetime_now_iso": {
            "description": "The offset date/time in ISO 8601 format.",
        },
        "datetime_now_epoch": {
            "description": "The offset date/time as a Unix epoch timestamp (float).",
        },
    }

    def main(self):
        """Execution starts here."""

        # coerce offset to float so recipe Input values (often strings) work
        try:
            offset_hours = float(self.env.get("datetime_offset_hours", 0) or 0)
        except (TypeError, ValueError) as err:
            raise ProcessorError(
                f"datetime_offset_hours must be a number: {err}"
            ) from err

        use_utc = bool(self.env.get("datetime_use_utc", False))
        strftime_format = self.env.get("datetime_strftime", "%Y-%m-%d %H:%M:%S")

        if use_utc:
            now = datetime.datetime.now(datetime.timezone.utc)
        else:
            # timezone-aware local time
            now = datetime.datetime.now().astimezone()

        result = now + datetime.timedelta(hours=offset_hours)

        self.env["datetime_now"] = result.strftime(strftime_format)
        self.env["datetime_now_iso"] = result.isoformat()
        self.env["datetime_now_epoch"] = result.timestamp()

        self.output(
            f"datetime_now: {self.env['datetime_now']} "
            f"(offset {offset_hours} hours, {'UTC' if use_utc else 'local'})"
        )


if __name__ == "__main__":
    PROCESSOR = GetDateTimeNow()
    PROCESSOR.execute_shell()
