#!/usr/bin/env bash
# Run the pytest suite using the most-preferred available Python interpreter.
#
# Interpreter preference order (the first one that exists AND can import pytest
# is used):
#   1. .venv/bin/python           (project virtualenv; Windows: .venv/Scripts/python)
#   2. /usr/local/autopkg/python  (AutoPkg-bundled python; ships autopkglib)
#   3. python3
#   4. python
#
# Any arguments are passed straight through to pytest, e.g.:
#   ./pytests_run.sh -k RecipeParentsInfo -v
#   ./pytests_run.sh tests/test_urldownloaderpython.py

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# macOS only: Homebrew installs native libraries (e.g. cairo, needed by cairosvg
# for the FileImageSvgToPng processor) under a prefix that dlopen() and
# ctypes.util.find_library() do not search by default. Add Homebrew's lib dir as
# a dyld fallback so those processors import instead of being skipped. Must be
# exported before Python launches (dyld reads it at process start).
if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    brew_lib="$(brew --prefix)/lib"
    export DYLD_FALLBACK_LIBRARY_PATH="${brew_lib}${DYLD_FALLBACK_LIBRARY_PATH:+:${DYLD_FALLBACK_LIBRARY_PATH}}"
fi

# In preference order. The two .venv entries are the same venv on Unix vs Windows.
candidates=(
    "${SCRIPT_DIR}/.venv/bin/python"
    "${SCRIPT_DIR}/.venv/Scripts/python"
    "/usr/local/autopkg/python"
    "python3"
    "python"
)

PYTHON=""
FALLBACK=""
for candidate in "${candidates[@]}"; do
    # Absolute paths must exist and be executable; bare names are resolved on PATH.
    if [[ "${candidate}" == */* ]]; then
        [[ -x "${candidate}" ]] || continue
        resolved="${candidate}"
    else
        resolved="$(command -v "${candidate}" 2>/dev/null || true)"
        [[ -n "${resolved}" ]] || continue
    fi
    # Remember the first interpreter that exists, as a fallback for messaging.
    [[ -z "${FALLBACK}" ]] && FALLBACK="${resolved}"
    # Prefer the first interpreter that can actually import pytest.
    if "${resolved}" -c "import pytest" >/dev/null 2>&1; then
        PYTHON="${resolved}"
        break
    fi
done

if [[ -z "${PYTHON}" ]]; then
    if [[ -n "${FALLBACK}" ]]; then
        echo "ERROR: none of the preferred interpreters have pytest installed." >&2
        echo "Install it, e.g.:  ${FALLBACK} -m pip install pytest" >&2
    else
        echo "ERROR: no suitable Python interpreter found (.venv, autopkg, python3, python)." >&2
    fi
    exit 1
fi

echo "Using Python: ${PYTHON}"
exec "${PYTHON}" -m pytest "$@"
