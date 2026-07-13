#!/usr/bin/env python3
"""Pre-commit hook: check AutoPkg recipes for cross-field conventions.

This is the recipe-level companion to autopkg_processor_check_conventions.py.
It is intentionally PICKY and OPINIONATED, but deliberately narrow: it only
checks things the JSON schema (.AutoPkgRecipeOpinionated.schema.json) *cannot*
express. JSON Schema (Draft 7, which check-jsonschema enforces here) validates
each field on its own -- it has no way to compare one field against another.
So the schema already covers structure and per-field patterns (Identifier
prefix, "no spaces", MinimumVersion shape, ...); this tool adds the CROSS-FIELD
checks it can't.

The flagship check (W110) is the one that prompted this tool: the `Identifier`
should refer to the `Input` `NAME`. It is checked with a NORMALIZED comparison
(case-folded, non-alphanumerics removed, a trailing "test"/"example" dropped
from NAME), because that is how this repo actually names recipes -- e.g. NAME
`FolderListFilesTest` pairs with identifier `com.github.jgstew.test.FolderListFiles`,
and NAME `Python3Win64` with `com.github.jgstew.download.Python3-Win64`. An exact
substring rule would misfire on more than half the repo; the normalized rule
leaves only a handful of genuine mismatches. Pass --exact to use the stricter
literal-substring rule instead.

A recipe is any file whose name ends in one of: .recipe.yaml, .recipe.yml, or
.recipe (the last is usually a plist; both plist and YAML are parsed).

Usage:
    autopkg_recipe_check_conventions.py [--strict] [--exact]
        [--disable W110] [Foo.download.recipe.yaml ...]

With no file arguments, all recipe files in the current folder and below are
checked. --disable takes a comma-separated list of check IDs to skip entirely.

Checks:
    W110  Identifier does not appear to reference the Input NAME (flagship)
    W100  recipe could not be parsed; skipped (advisory -- check-yaml /
          validate-plist are the authorities on file validity)
    W101  PyYAML is not available, so a YAML recipe could not be parsed; skipped
    W102  top-level of the recipe is not a mapping; skipped

Warnings are advisory and do NOT fail the hook, so wire the hook with
`verbose: true` to surface them. Pass --strict to turn every warning into a
failure (non-zero exit) -- useful in CI.

A file can opt out of all checks with a comment anywhere in it:
    # pre-commit-skip: recipe-conventions
and out of just the NAME/Identifier check with:
    # identifier-name-ok

Exit codes:
    0  no failures (warnings alone do not fail unless --strict)
    1  a warning was raised while --strict is set
"""

import argparse
import os
import plistlib
import re
import sys

try:
    import yaml
except ImportError:  # PyYAML may be absent in a bare environment; degrade to W101
    yaml = None

SKIP_MARKER = "pre-commit-skip: recipe-conventions"

# File-level opt-out for the NAME/Identifier check (W110), for a recipe whose
# identifier intentionally does not track its NAME.
IDENTIFIER_NAME_MARKER = "identifier-name-ok"

# The extensions that make a file an AutoPkg recipe. `.recipe` is usually a
# plist; the `.recipe.y{a,}ml` forms are YAML. Order matters for endswith().
RECIPE_EXTENSIONS = (".recipe.yaml", ".recipe.yml", ".recipe")

# Suffixes stripped from a normalized NAME before comparing to the identifier:
# test/example recipes name their NAME `<Thing>Test` / `<Thing>Example` while
# the identifier carries `<Thing>` in the `.test.`/`.example.` component.
NAME_CORE_SUFFIXES = ("test", "example")

# Every check ID this tool can emit -- used to validate --disable arguments so a
# typo (e.g. "W99") is reported rather than silently ignored.
KNOWN_CODES = frozenset(
    [
        "W100",  # could not parse recipe
        "W101",  # PyYAML unavailable
        "W102",  # top-level is not a mapping
        "W110",  # Identifier does not reference the Input NAME
    ]
)


def normalize(value):
    """Return `value` lowercased with every non-alphanumeric character removed.

    This collapses the cosmetic differences (case, dots, hyphens, underscores)
    between a NAME and an Identifier so only the meaningful characters remain.
    """
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def name_core(name):
    """Return the normalized NAME with a trailing test/example suffix removed.

    `FolderListFilesTest` -> `folderlistfiles`; `AutoPkgCacheCleanupExample` ->
    `autopkgcachecleanup`. The suffix is only stripped when something remains,
    so a NAME that is literally "Test" is left intact.
    """
    core = normalize(name)
    for suffix in NAME_CORE_SUFFIXES:
        if core.endswith(suffix) and len(core) > len(suffix):
            return core[: -len(suffix)]
    return core


def find_line(source_lines, *patterns):
    """Return the 1-based line of the first line matching any regex, else 1.

    Used only to point the reader at the relevant line (e.g. the `Identifier:`
    line in YAML, or `<key>Identifier</key>` in a plist); a miss falls back to
    line 1 rather than failing.
    """
    for index, line in enumerate(source_lines, start=1):
        if any(re.search(pattern, line) for pattern in patterns):
            return index
    return 1


def parse_recipe(src):
    """Parse recipe source into a Python object.

    Returns (data, warning) where exactly one is set: `data` is the parsed
    object on success, or `warning` is a (check_id, message) tuple describing
    why parsing was skipped. Plist (`<?xml`/`<plist`) is detected by a leading
    `<`; everything else is treated as YAML.
    """
    if src.lstrip().startswith("<"):
        try:
            return plistlib.loads(src.encode("utf-8")), None
        except (ValueError, plistlib.InvalidFileException) as err:
            return None, ("W100", f"could not parse plist recipe: {err}")
    if yaml is None:
        return None, ("W101", "PyYAML not available; YAML recipe skipped")
    try:
        return yaml.safe_load(src), None
    except yaml.YAMLError as err:
        detail = str(err).splitlines()[0] if str(err) else "invalid YAML"
        return None, ("W100", f"could not parse YAML recipe: {detail}")


# --- individual checks -------------------------------------------------------
# Each returns a (possibly empty) list of (lineno, check_id, message) tuples and
# never mutates anything, so they can be read, tested, and reordered in
# isolation. check_file just calls them in order and concatenates the results.


def check_identifier_references_name(recipe, source_lines, exact):
    """W110: the Identifier should reference the Input NAME.

    Skipped when either value is missing (the schema's `required` handles that)
    or when NAME is empty. In the default (normalized) mode the NAME core must
    appear inside the normalized identifier; with `exact` the raw NAME must be a
    literal substring of the raw identifier. A recipe that intentionally breaks
    the convention can carry the `# identifier-name-ok` comment to opt out.
    """
    identifier = recipe.get("Identifier")
    input_block = recipe.get("Input")
    name = input_block.get("NAME") if isinstance(input_block, dict) else None
    if not isinstance(identifier, str) or not name:
        return []

    if exact:
        matches = str(name) in identifier
        how = "as a substring (exact)"
    else:
        matches = bool(name_core(name)) and name_core(name) in normalize(identifier)
        how = "(normalized: case/punctuation-insensitive)"
    if matches:
        return []

    lineno = find_line(source_lines, r"^\s*Identifier\s*:", r"<key>Identifier</key>")
    return [
        (
            lineno,
            "W110",
            f"Identifier `{identifier}` does not reference the Input NAME "
            f"`{name}` {how}; add `# {IDENTIFIER_NAME_MARKER}` if intentional",
        )
    ]


def check_file(path, strict=False, exact=False, disabled=frozenset()):
    """Check one recipe file; return a list of (lineno, check_id, message).

    `strict` and `exact` tune the flagship check (see module docstring).
    `disabled` is a set of check IDs to skip. The body is just orchestration:
    guard the path, parse the recipe, then run the pure check_* helpers.
    """
    if not os.path.isfile(path):
        return [(1, "W100", "file not found; skipping")]

    with open(path, encoding="utf-8", errors="replace") as handle:
        src = handle.read()

    if SKIP_MARKER in src:
        return []

    data, warning = parse_recipe(src)
    if warning is not None:
        return [(1, warning[0], warning[1])]
    if not isinstance(data, dict):
        return [(1, "W102", "top-level of recipe is not a mapping; skipping")]

    source_lines = src.splitlines()
    issues = []

    if "W110" not in disabled and IDENTIFIER_NAME_MARKER not in src:
        issues += check_identifier_references_name(data, source_lines, exact)

    return sorted(issues)


def is_recipe_file(path):
    """True if `path` has one of the recognized recipe extensions."""
    return path.endswith(RECIPE_EXTENSIONS)


def check_files(paths, strict=False, exact=False, disabled=frozenset()):
    """Check several recipe files; return a list of (path, issues) tuples.

    Non-recipe paths are skipped. Disabled codes are filtered from the results.
    This is the programmatic entry point: it does no printing, so other code can
    consume the structured results. `main()` wraps it to print and exit.
    """
    results = []
    for path in paths:
        if not is_recipe_file(path):
            continue
        issues = check_file(path, strict=strict, exact=exact, disabled=disabled)
        issues = [item for item in issues if item[1] not in disabled]
        results.append((path, issues))
    return results


def discover_recipe_files(root="."):
    """Return all recipe files under `root`.

    Hidden directories and common noise (__pycache__, node_modules) are pruned.
    Unlike the processor checker there is no depth limit -- recipes live at
    varying depths (e.g. BigFix/QnA.pkg.recipe, Test-Recipes/Foo.test.recipe.yaml).
    """
    skip_dirs = {"__pycache__", "node_modules"}
    root = os.path.normpath(root)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") and d not in skip_dirs
        ]
        for name in filenames:
            if is_recipe_file(name):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def main(argv=None):
    """Execution starts here.

    argv defaults to None so this works both as a console_scripts entry point
    (pre-commit calls it with no arguments; argparse then reads sys.argv) and
    when called directly as `main(sys.argv[1:])`.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures (non-zero exit); default: advisory",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="require the Input NAME to be a literal substring of the Identifier "
        "instead of the default normalized comparison",
    )
    parser.add_argument(
        "--disable",
        default="",
        metavar="CODES",
        help="comma-separated check IDs to skip entirely, e.g. --disable W110",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="recipe files to check; if omitted, all recipe files in the current "
        "folder and below are checked",
    )
    args = parser.parse_args(argv)

    disabled = {
        code.strip().upper() for code in args.disable.split(",") if code.strip()
    }
    unknown = disabled - KNOWN_CODES
    if unknown:
        print(
            f"warning: ignoring unknown --disable code(s): {', '.join(sorted(unknown))}"
        )

    paths = args.files if args.files else discover_recipe_files(".")

    warning_count = 0
    for path, issues in check_files(
        paths, strict=args.strict, exact=args.exact, disabled=disabled
    ):
        for lineno, check_id, message in issues:
            warning_count += 1
            print(f"{path}:{lineno}: [{check_id}] warning: {message}")

    if warning_count:
        print(f"\n{warning_count} recipe-convention warning(s).")
    # warnings fail the hook only under --strict
    return 1 if (warning_count and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
