#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for FileYamlRead class"""

# Related:
# - https://github.com/autopkg/jgstew-recipes/blob/main/SharedProcessors/JsonPath.py

import os

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)
from ruamel.yaml import YAML  # already a dependency of AutoPkg itself

__all__ = ["FileYamlRead"]


class FileYamlRead(Processor):  # pylint: disable=invalid-name
    """Reads a YAML file (or YAML string) with ruamel.yaml and returns either the
    whole parsed document or the value at a dotted key path (e.g. `nested.host` or
    `items.0.name`) as an output variable.
    """

    description = __doc__
    input_variables = {
        "yaml_input": {
            "required": True,
            "description": "Path to a YAML file to read, or a YAML-formatted string.",
        },
        "yaml_key": {
            "required": False,
            "default": "",
            "description": (
                "Optional dotted path to a value within the document, e.g."
                " `nested.host` or `items.0.name` (integer segments index into"
                " lists). If empty, the whole parsed document is returned."
            ),
        },
    }
    output_variables = {
        "yaml_read_result": {
            "description": "The whole parsed document, or the value at yaml_key.",
        },
    }

    def get_dotted(self, data, dotted_key):
        """Return the value at a dotted key path within nested dicts/lists."""
        value = data
        for segment in dotted_key.split("."):
            if isinstance(value, list):
                try:
                    value = value[int(segment)]
                except (ValueError, IndexError) as err:
                    raise ProcessorError(
                        f"yaml_key segment '{segment}' is not a valid list index"
                    ) from err
            elif isinstance(value, dict):
                if segment not in value:
                    raise ProcessorError(
                        f"yaml_key segment '{segment}' not found in the document"
                    )
                value = value[segment]
            else:
                raise ProcessorError(
                    f"yaml_key segment '{segment}' cannot index a"
                    f" {type(value).__name__}"
                )
        return value

    def main(self):
        """Execution starts here."""
        # Reading input_variables
        yaml_input = self.env.get("yaml_input")
        yaml_key = self.env.get("yaml_key", "")

        # safe load -> plain dict/list/scalar types (no round-trip needed to read)
        yaml_reader = YAML(typ="safe")

        # Load from a file if it exists, otherwise treat the input as a YAML string.
        if os.path.isfile(yaml_input):
            with open(yaml_input, encoding="utf-8") as yaml_file:
                data = yaml_reader.load(yaml_file)
        else:
            data = yaml_reader.load(yaml_input)

        # Navigate to the requested key, if any.
        yaml_read_result = self.get_dotted(data, yaml_key) if yaml_key else data

        self.output(yaml_read_result, 4)

        # Writing output_variables
        self.env["yaml_read_result"] = yaml_read_result


if __name__ == "__main__":
    PROCESSOR = FileYamlRead()
    PROCESSOR.execute_shell()
