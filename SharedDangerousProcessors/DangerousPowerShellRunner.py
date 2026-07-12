#!/usr/local/autopkg/python
#
# James Stewart @JGStew - 2026
#
"""See docstring for DangerousPowerShellRunner class"""

import os
import platform
import shutil
import subprocess

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)

__all__ = ["DangerousPowerShellRunner"]


class DangerousPowerShellRunner(Processor):  # pylint: disable=invalid-name
    """Runs PowerShell via subprocess.

    `powershell_script` is auto-detected: if it is a path to an existing file it
    is run as a script file (-File), otherwise it is run as inline script text
    (-Command).

    Defaults to the cross-platform PowerShell (`pwsh`, available on macOS, Linux,
    and Windows). Set `use_windows_powershell` to prefer Windows PowerShell
    (`powershell.exe`) when running on Windows, or set `powershell_executable` to
    an explicit interpreter path. On Windows, if the preferred interpreter is not
    found the other is tried as a fallback.

    You should probably not use this processor, as it is dangerous: it executes
    arbitrary PowerShell. It is intended for testing/automation glue, not for
    untrusted input, and is not recommended in production recipes."""

    description = __doc__
    input_variables = {
        "powershell_script": {
            "required": True,
            "description": (
                "The PowerShell to run. If this value is a path to an existing "
                "file on disk it is run as a script file (via -File); otherwise "
                "it is treated as inline PowerShell script text (via -Command)."
            ),
        },
        "powershell_args": {
            "required": False,
            "default": [],
            "description": "Optional array of arguments passed to the script.",
        },
        "powershell_executable": {
            "required": False,
            "default": "",
            "description": (
                "Explicit PowerShell interpreter (name on PATH or full path). "
                "Overrides the pwsh/powershell auto-selection when set."
            ),
        },
        "use_windows_powershell": {
            "required": False,
            "default": False,
            "description": (
                "If True and running on Windows, use Windows PowerShell "
                "(powershell.exe) instead of the default cross-platform pwsh."
            ),
        },
        "powershell_execution_policy": {
            "required": False,
            "default": "Bypass",
            "description": (
                "Value passed as -ExecutionPolicy (applied on Windows only). "
                "Default: Bypass."
            ),
        },
        "powershell_ignore_errors": {
            "required": False,
            "default": False,
            "description": (
                "If True, a non-zero exit code is reported but does not raise a "
                "ProcessorError. Default: False."
            ),
        },
    }
    output_variables = {
        "powershell_output": {
            "description": "Captured stdout of the PowerShell run.",
        },
        "powershell_return_code": {
            "description": "The process exit code (integer).",
        },
        "powershell_executable_used": {
            "description": "The resolved PowerShell interpreter path that was run.",
        },
    }

    def resolve_executable(self):
        """Return the resolved PowerShell interpreter path, or raise if not found.

        Honors an explicit `powershell_executable`; otherwise uses Windows
        PowerShell when `use_windows_powershell` is set on Windows, else the
        cross-platform `pwsh`. On Windows, falls back to the other interpreter if
        the preferred one is not on PATH.
        """
        explicit = self.env.get("powershell_executable", "")
        use_windows = bool(self.env.get("use_windows_powershell", False))
        is_windows = platform.system() == "Windows"

        if explicit:
            candidate = explicit
        elif use_windows and is_windows:
            candidate = "powershell"
        else:
            candidate = "pwsh"

        resolved = shutil.which(candidate)
        if resolved is None and is_windows and not explicit:
            # fall back to the other interpreter on Windows
            other = (
                "pwsh" if candidate.lower().startswith("powershell") else "powershell"
            )
            resolved = shutil.which(other)
            if resolved:
                candidate = other
        if resolved is None:
            raise ProcessorError(f"PowerShell interpreter not found: {candidate}")
        return resolved

    def main(self):
        """Execution starts here."""
        script = self.env.get("powershell_script")
        args = [str(arg) for arg in (self.env.get("powershell_args") or [])]
        execution_policy = self.env.get("powershell_execution_policy", "Bypass")
        ignore_errors = bool(self.env.get("powershell_ignore_errors", False))

        if not script:
            raise ProcessorError("powershell_script is required")

        # If the value points at an existing file, run it as a script file;
        # otherwise treat it as inline PowerShell script text.
        is_file = isinstance(script, str) and os.path.isfile(script)

        executable = self.resolve_executable()
        is_windows = platform.system() == "Windows"

        command = [executable, "-NoProfile"]
        if is_windows:
            command += ["-ExecutionPolicy", execution_policy]
        if is_file:
            command += ["-File", script]
        else:
            command += ["-Command", script]
        command += args

        mode = "script file" if is_file else "inline command"
        self.output(f"running PowerShell ({mode}) via {executable}", 2)
        try:
            proc = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as err:
            raise ProcessorError(f"PowerShell execution failed: {err}") from err

        self.env["powershell_executable_used"] = executable
        self.env["powershell_return_code"] = proc.returncode
        self.env["powershell_output"] = proc.stdout

        self.output(f"return code: {proc.returncode}", 2)
        self.output(f"output:\n{proc.stdout}", 3)

        if proc.returncode != 0 and not ignore_errors:
            raise ProcessorError(
                f"PowerShell exited {proc.returncode}\nstderr: {proc.stderr}\n"
                f"stdout: {proc.stdout}"
            )


if __name__ == "__main__":
    PROCESSOR = DangerousPowerShellRunner()
    PROCESSOR.execute_shell()
