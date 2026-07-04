#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for FileYamlReadYq class"""

# Queries YAML with the `yq` binary (Mike Farah's Go yq, v4+), which reads YAML
# natively and can emit YAML or JSON.
# Install:
#   macOS:   brew install yq
#   Windows: choco install yq -y
#   Linux:   snap install yq   (or download the release binary)
# Related:
# - https://github.com/autopkg/jgstew-recipes/blob/main/SharedProcessors/JsonJq.py
# - https://github.com/mikefarah/yq

import os
import shutil
import subprocess

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)

__all__ = ["FileYamlReadYq"]

# common install locations for the yq binary, searched after PATH
YQ_BIN_PATHS = [
    "yq",
    "/usr/bin/yq",
    "/usr/local/bin/yq",
    "/opt/homebrew/bin/yq",
    "/ProgramData/chocolatey/bin/yq",
]


class FileYamlReadYq(Processor):  # pylint: disable=invalid-name
    """Evaluates a `yq` expression against a YAML file or YAML string and returns
    the result. Uses Mike Farah's `yq` binary, which reads YAML natively and can
    output either YAML or JSON.
    """

    description = __doc__
    input_variables = {
        "yaml_input": {
            "required": True,
            "description": "Path to a YAML file, or a YAML-formatted string, to query.",
        },
        "yq_expression": {
            "required": False,
            "default": ".",
            "description": (
                "The yq expression to evaluate, e.g. `.nested.host` or"
                " `.items[0].name`. Defaults to `.` (the whole document)."
            ),
        },
        "output_format": {
            "required": False,
            "default": "yaml",
            "description": "Output format from yq: `yaml` (default) or `json`.",
        },
        "yq_bin_path": {
            "required": False,
            "default": "yq",
            "description": (
                "Path to the yq binary; falls back to PATH and common install"
                " locations."
            ),
        },
    }
    output_variables = {
        "yaml_yq_result": {"description": "The result of the yq expression."},
        "yq_bin_path": {"description": "The yq binary that was used."},
    }

    def find_yq(self, preferred):
        """Return a usable yq binary path, or raise ProcessorError if none found."""
        for candidate in [preferred, *YQ_BIN_PATHS]:
            if not candidate:
                continue
            found = shutil.which(candidate)
            if found:
                return found
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        raise ProcessorError(
            "yq binary not found. Install it (macOS: `brew install yq`, Windows:"
            " `choco install yq`, Linux: `snap install yq`)."
        )

    def main(self):
        """Execution starts here."""
        # Reading input_variables
        yaml_input = self.env.get("yaml_input")
        yq_expression = self.env.get("yq_expression", ".")
        output_format = self.env.get("output_format", "yaml")
        yq_bin_path = self.find_yq(self.env.get("yq_bin_path", "yq"))

        command = [yq_bin_path, "--output-format", output_format, yq_expression]

        # Pass a file path directly to yq; feed a raw string via stdin (no temp file).
        if os.path.isfile(yaml_input):
            command.append(yaml_input)
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        else:
            result = subprocess.run(
                command,
                input=yaml_input,
                capture_output=True,
                text=True,
                check=False,
            )

        if result.returncode != 0:
            raise ProcessorError(
                f"yq failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        yaml_yq_result = result.stdout.rstrip("\n")

        self.output(yaml_yq_result, 2)

        # Writing output_variables
        self.env["yaml_yq_result"] = yaml_yq_result
        self.env["yq_bin_path"] = yq_bin_path


if __name__ == "__main__":
    PROCESSOR = FileYamlReadYq()
    PROCESSOR.execute_shell()
