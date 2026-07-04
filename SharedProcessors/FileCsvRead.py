#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for FileCsvRead class"""

# Related:
# - https://github.com/autopkg/jgstew-recipes/blob/main/SharedProcessors/FileConfigParser.py
# - https://docs.python.org/3/library/csv.html

import csv
import io
import os

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)

__all__ = ["FileCsvRead"]


class FileCsvRead(Processor):  # pylint: disable=invalid-name
    """Reads values from a CSV/TSV file (or CSV string) with Python's csv module.
    Selects a single cell (row + column), a whole column, a whole row, or all rows,
    and stores the result in the env variable named by csv_output_variable.
    """

    description = __doc__
    input_variables = {
        "csv_input": {
            "required": True,
            "description": "Path to a CSV file, or a CSV-formatted string, to read.",
        },
        "csv_row": {
            "required": False,
            "default": "",
            "description": (
                "0-based row index into the data rows (negative indexes from the"
                " end). With csv_column it selects a single cell; alone it returns"
                " the whole row. Empty selects no specific row."
            ),
        },
        "csv_column": {
            "required": False,
            "default": "",
            "description": (
                "Column to read: a header name (when has_header is true) or a"
                " 0-based column index. With csv_row it selects a single cell; alone"
                " it returns the whole column. Empty selects no specific column."
            ),
        },
        "has_header": {
            "required": False,
            "default": True,
            "description": "Whether the first row is a header row. Default: true.",
        },
        "delimiter": {
            "required": False,
            "default": ",",
            "description": (
                "Field delimiter. Use `\\t` or `tab` for tab-separated (TSV)."
                " Default: `,`."
            ),
        },
        "csv_output_variable": {
            "required": False,
            "default": "csv_result",
            "description": (
                "Name of the env variable to store the result in. Default:"
                " `csv_result`."
            ),
        },
    }
    output_variables = {
        "csv_result": {
            "description": (
                "The selected value(s): a single cell (string), a column (list), a"
                " row (dict when has_header, else list), or all rows. Written to the"
                " env variable named by csv_output_variable."
            ),
        },
    }

    def resolve_column(self, header, column):
        """Return the integer column index for a header name or an index string."""
        if header and column in header:
            return header.index(column)
        try:
            return int(column)
        except (TypeError, ValueError) as err:
            raise ProcessorError(
                f"csv_column '{column}' is not a header name or a column index"
            ) from err

    def main(self):
        """Execution starts here."""
        # Reading input_variables
        csv_input = self.env.get("csv_input")
        csv_row = self.env.get("csv_row", "")
        csv_column = self.env.get("csv_column", "")
        has_header = bool(self.env.get("has_header", True))
        delimiter = self.env.get("delimiter", ",")
        csv_output_variable = self.env.get("csv_output_variable", "csv_result")

        # allow friendly tab spellings for TSV
        if delimiter in ("\\t", "tab"):
            delimiter = "\t"

        # read from a file if it exists, otherwise treat the input as CSV text
        if os.path.isfile(csv_input):
            with open(csv_input, newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle, delimiter=delimiter))
        else:
            rows = list(csv.reader(io.StringIO(csv_input), delimiter=delimiter))

        if not rows:
            raise ProcessorError(f"no rows found in csv_input: {csv_input}")

        header = rows[0] if has_header else None
        data = rows[1:] if has_header else rows

        row_given = csv_row != ""
        col_given = csv_column != ""

        row_index = None
        if row_given:
            try:
                row_index = int(csv_row)
            except (TypeError, ValueError) as err:
                raise ProcessorError(f"csv_row '{csv_row}' is not an integer") from err
            if not -len(data) <= row_index < len(data):
                raise ProcessorError(f"csv_row {row_index} is out of range")

        try:
            if row_given and col_given:
                result = data[row_index][self.resolve_column(header, csv_column)]
            elif col_given:
                col_index = self.resolve_column(header, csv_column)
                result = [row[col_index] for row in data]
            elif row_given:
                row = data[row_index]
                result = dict(zip(header, row)) if header else row
            else:
                result = [dict(zip(header, r)) for r in data] if header else data
        except IndexError as err:
            raise ProcessorError(f"csv_column '{csv_column}' is out of range") from err

        self.output(result, 3)
        self.env[csv_output_variable] = result


if __name__ == "__main__":
    PROCESSOR = FileCsvRead()
    PROCESSOR.execute_shell()
