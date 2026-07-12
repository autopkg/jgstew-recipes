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
    """Runs a PowerShell script (inline text or a .ps1 file) via subprocess.

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
            "required": False,
            "description": (
                "Inline PowerShell script text to run (via -Command). Provide "
                "this or powershell_script_path; powershell_script_path wins if "
                "both are set."
            ),
        },
        "powershell_script_path": {
            "required": False,
            "description": "Path to a .ps1 script file to run (via -File).",
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
        script_path = self.env.get("powershell_script_path")
        args = [str(arg) for arg in (self.env.get("powershell_args") or [])]
        execution_policy = self.env.get("powershell_execution_policy", "Bypass")
        ignore_errors = bool(self.env.get("powershell_ignore_errors", False))

        if script_path and not os.path.isfile(script_path):
            raise ProcessorError(f"powershell_script_path not found: {script_path}")
        if not script_path and not script:
            raise ProcessorError(
                "provide powershell_script (inline) or powershell_script_path"
            )

        executable = self.resolve_executable()
        is_windows = platform.system() == "Windows"

        command = [executable, "-NoProfile"]
        if is_windows:
            command += ["-ExecutionPolicy", execution_policy]
        if script_path:
            command += ["-File", script_path]
        else:
            command += ["-Command", script]
        command += args

        self.output(f"running PowerShell via {executable}", 2)
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
