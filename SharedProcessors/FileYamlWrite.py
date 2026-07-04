#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for FileYamlWrite class"""

# Related:
# - https://github.com/autopkg/jgstew-recipes/blob/main/SharedProcessors/JSONWriter.py
# - https://github.com/autopkg/jgstew-recipes/blob/main/SharedProcessors/FileYamlRead.py

import io
import os

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)
from ruamel.yaml import YAML  # round-trip YAML that preserves comments/formatting

__all__ = ["FileYamlWrite"]


class FileYamlWrite(Processor):  # pylint: disable=invalid-name
    """Writes YAML to a file using ruamel.yaml. When yaml_key is given, only that
    dotted key is updated within an existing file, preserving its comments and
    formatting; otherwise yaml_input is written as the entire document.
    """

    description = __doc__
    input_variables = {
        "yaml_output_path": {
            "required": True,
            "description": "File path to write the YAML output to.",
        },
        "yaml_input": {
            "required": True,
            "description": (
                "The value to write: a dictionary/list/scalar, or a YAML-formatted"
                " string (which is parsed first). When yaml_key is set, this is the"
                " value stored at that key."
            ),
        },
        "yaml_key": {
            "required": False,
            "default": "",
            "description": (
                "Optional dotted path to set within the file (e.g. `nested.host`),"
                " preserving the rest of the file. If empty, the whole file is"
                " replaced with yaml_input."
            ),
        },
    }
    output_variables = {
        "yaml_output_path": {
            "description": "The path of the YAML file that was written.",
        },
    }

    def set_dotted(self, data, dotted_key, value):
        """Set `value` at a dotted key path, creating intermediate dicts as needed."""
        segments = dotted_key.split(".")
        cursor = data
        for segment in segments[:-1]:
            if isinstance(cursor, list):
                cursor = cursor[int(segment)]
            else:
                if segment not in cursor or not isinstance(
                    cursor[segment], (dict, list)
                ):
                    cursor[segment] = {}
                cursor = cursor[segment]
        last = segments[-1]
        if isinstance(cursor, list):
            cursor[int(last)] = value
        else:
            cursor[last] = value

    def main(self):
        """Execution starts here."""
        # Reading input_variables
        yaml_output_path = self.env.get("yaml_output_path")
        yaml_input = self.env.get("yaml_input")
        yaml_key = self.env.get("yaml_key", "")

        yaml_rt = YAML()  # round-trip mode preserves comments and formatting
        yaml_rt.preserve_quotes = True

        # If yaml_input is a string, parse it into a data structure first.
        if isinstance(yaml_input, str):
            yaml_input = yaml_rt.load(yaml_input)

        if yaml_key:
            # update a single key within the existing file (or a new document)
            if os.path.isfile(yaml_output_path):
                with open(yaml_output_path, encoding="utf-8") as yaml_file:
                    data = yaml_rt.load(yaml_file) or {}
            else:
                data = {}
            self.set_dotted(data, yaml_key, yaml_input)
        else:
            data = yaml_input

        with open(yaml_output_path, "w", encoding="utf-8") as yaml_file:
            yaml_rt.dump(data, yaml_file)

        self.output(f"Wrote YAML to: {yaml_output_path}")
        # echo what was written at higher verbosity
        buffer = io.StringIO()
        yaml_rt.dump(data, buffer)
        self.output(buffer.getvalue(), 4)

        # Writing output_variables
        self.env["yaml_output_path"] = yaml_output_path


if __name__ == "__main__":
    PROCESSOR = FileYamlWrite()
    PROCESSOR.execute_shell()
