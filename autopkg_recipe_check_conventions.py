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

A second cross-field check (W111) verifies that every `ParentRecipe` resolves:
its value should be the `Identifier` of some recipe in this repo. (AutoPkg will
also accept a ParentRecipe given as a file path, but only relative to the
working directory it runs from -- fragile and non-portable -- so a path-like
value is flagged with a hint to use the identifier instead.) The check is built
from a repo-wide index of every recipe's Identifier, so it works even when
pre-commit only passes the changed files. W111 is AUTO-FIXABLE: when a
ParentRecipe is a path that points at a recipe whose Identifier can be read, it
is rewritten in place to that Identifier (see --auto-fix).

Usage:
    autopkg_recipe_check_conventions.py [--strict] [--exact]
        [--auto-fix=yes|no] [--disable W110,W111] [Foo.download.recipe.yaml ...]

With no file arguments, all recipe files in the current folder and below are
checked. --disable takes a comma-separated list of check IDs to skip entirely.
--auto-fix rewrites a fixable path-like ParentRecipe (W111) in place; it defaults
to yes when files are given explicitly, but to no when auto-discovering, so a
bare run is read-only. An auto-fixed file fails the hook so the change is
reviewed and re-staged.

Checks:
    W110  Identifier does not appear to reference the Input NAME (flagship)
    W111  ParentRecipe does not resolve to a known recipe Identifier
    W100  recipe could not be parsed; skipped (advisory -- check-yaml /
          validate-plist are the authorities on file validity)
    W101  PyYAML is not available, so a YAML recipe could not be parsed; skipped
    W102  top-level of the recipe is not a mapping; skipped

Warnings are advisory and do NOT fail the hook, so wire the hook with
`verbose: true` to surface them. Pass --strict to turn every warning into a
failure (non-zero exit) -- useful in CI.

A file can opt out of all checks with a comment anywhere in it:
    # pre-commit-skip: recipe-conventions
out of just the NAME/Identifier check with:
    # identifier-name-ok
and out of just the ParentRecipe check (e.g. a parent defined in another repo)
with:
    # parent-recipe-ok

Exit codes:
    0  no failures (warnings alone do not fail unless --strict)
    1  a file was auto-fixed, or a warning was raised while --strict is set
"""

import argparse
import collections
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

# File-level opt-out for the ParentRecipe check (W111), for a recipe whose
# parent is legitimately defined outside this repo (so it is not in the index).
PARENT_RECIPE_MARKER = "parent-recipe-ok"

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
        "W111",  # ParentRecipe does not resolve to a known Identifier
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


def check_parent_recipe_resolvable(recipe, source_lines, identifier_index):
    """W111: a `ParentRecipe` should resolve to a known recipe Identifier.

    The `ParentRecipe` value should match the `Identifier` of some recipe in
    `identifier_index` (built from the whole repo). Matching is case-sensitive,
    as AutoPkg's is. Skipped when there is no ParentRecipe, when it is not a
    string, or when the index is unavailable.

    Note: AutoPkg's locate_recipe() tries `os.path.isfile(name)` before its
    identifier search, so a ParentRecipe given as a file path can still resolve
    -- but only relative to the working directory autopkg runs from, which is
    fragile and non-portable. So a path-like value is flagged with a hint to use
    the parent's identifier instead, rather than reported as strictly broken.
    """
    parent = recipe.get("ParentRecipe")
    if not isinstance(parent, str) or not parent:
        return []
    if parent in identifier_index:
        return []

    looks_like_path = "/" in parent or parent.endswith(RECIPE_EXTENSIONS)
    hint = (
        " (it looks like a file path -- AutoPkg only resolves that relative to "
        "the working directory; use the parent's Identifier instead)"
        if looks_like_path
        else ""
    )
    lineno = find_line(
        source_lines, r"^\s*ParentRecipe\s*:", r"<key>ParentRecipe</key>"
    )
    return [
        (
            lineno,
            "W111",
            f"ParentRecipe `{parent}` does not match any recipe Identifier "
            f"in this repo{hint}; add `# {PARENT_RECIPE_MARKER}` if the parent is "
            "defined elsewhere",
        )
    ]


# The repo-wide recipe index: `identifiers` is the set of every recipe
# Identifier; `by_path` maps each recipe's normalized relative path to its
# Identifier (so a ParentRecipe given as a file path can be resolved back to the
# identifier it should have been). Both are built in one scan.
RecipeIndex = collections.namedtuple("RecipeIndex", ["identifiers", "by_path"])


def build_recipe_index(root="."):
    """Return a RecipeIndex of every recipe under `root`.

    Scans all recipe files (regardless of which files are being checked) so the
    ParentRecipe check can resolve against the whole repo even when pre-commit
    passes only the changed files. Files that fail to parse or lack a string
    Identifier simply do not contribute; the skip marker does not exclude a file
    here (it still defines an identifier a parent may legitimately point at).
    """
    identifiers = set()
    by_path = {}
    for path in discover_recipe_files(root):
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                src = handle.read()
        except OSError:
            continue
        data, _ = parse_recipe(src)
        if isinstance(data, dict) and isinstance(data.get("Identifier"), str):
            identifier = data["Identifier"]
            identifiers.add(identifier)
            by_path[os.path.normpath(path)] = identifier
    return RecipeIndex(identifiers, by_path)


def resolve_parent_path_to_identifier(recipe_path, parent_value, index):
    """Return the Identifier the path-like `parent_value` points at, or None.

    Tries the value as a path relative to the working directory and relative to
    the recipe's own folder; failing that, falls back to a unique basename match
    among indexed recipes. Returns None when nothing (or more than one thing)
    matches, so the fixer leaves an unresolvable value alone for a human.
    """
    candidates = [
        os.path.normpath(parent_value),
        os.path.normpath(os.path.join(os.path.dirname(recipe_path), parent_value)),
    ]
    for candidate in candidates:
        if candidate in index.by_path:
            return index.by_path[candidate]

    base = os.path.basename(parent_value)
    matches = {
        identifier
        for path, identifier in index.by_path.items()
        if os.path.basename(path) == base
    }
    if len(matches) == 1:
        return next(iter(matches))
    return None


def apply_parent_recipe_fix(path, new_identifier):
    """Rewrite the file's ParentRecipe value in place to `new_identifier`.

    Handles both YAML (`ParentRecipe: <value>`, preserving indentation and any
    trailing comment) and plist (`<key>ParentRecipe</key><string>...</string>`).
    Only the value is changed; nothing else in the file is touched.
    """
    with open(path, encoding="utf-8") as handle:
        src = handle.read()

    if src.lstrip().startswith("<"):
        new_src = re.sub(
            r"(<key>ParentRecipe</key>\s*<string>)(.*?)(</string>)",
            lambda m: m.group(1) + new_identifier + m.group(3),
            src,
            count=1,
            flags=re.DOTALL,
        )
    else:
        lines = src.split("\n")
        for i, line in enumerate(lines):
            # group1 = key/colon/spaces, group2 = the (space-free) value token,
            # group3 = any trailing whitespace/comment to preserve verbatim
            match = re.match(r"^(\s*ParentRecipe\s*:\s*)(\S+)(.*)$", line)
            if match:
                lines[i] = match.group(1) + new_identifier + match.group(3)
                break
        new_src = "\n".join(lines)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(new_src)


def maybe_fix_parent_recipe(path, recipe, index):
    """Auto-fix W111: rewrite a path-like ParentRecipe to the parent's Identifier.

    Acts only when the ParentRecipe value is not already a known Identifier AND it
    resolves (as a path) to a recipe whose Identifier we can read. Anything not so
    resolvable is left untouched (and stays reported as W111). Returns the list of
    fixed entries (empty when nothing was fixed).
    """
    parent = recipe.get("ParentRecipe")
    if not isinstance(parent, str) or not parent:
        return []
    if parent in index.identifiers:
        return []  # already a valid identifier; nothing to fix
    new_identifier = resolve_parent_path_to_identifier(path, parent, index)
    if not new_identifier or new_identifier == parent:
        return []  # cannot resolve to a known identifier -> leave for a human

    with open(path, encoding="utf-8", errors="replace") as handle:
        source_lines = handle.read().splitlines()
    lineno = find_line(
        source_lines, r"^\s*ParentRecipe\s*:", r"<key>ParentRecipe</key>"
    )
    apply_parent_recipe_fix(path, new_identifier)
    return [
        (
            lineno,
            "W111",
            f"rewrote ParentRecipe path `{parent}` to identifier `{new_identifier}`",
        )
    ]


def check_file(
    path,
    strict=False,
    exact=False,
    disabled=frozenset(),
    recipe_index=None,
    auto_fix=False,
):
    """Check one recipe file; return (issues, fixed).

    Each of `issues` and `fixed` is a list of (lineno, check_id, message).
    `strict` and `exact` tune the flagship check (see module docstring).
    `disabled` is a set of check IDs to skip. `recipe_index` is the repo-wide
    RecipeIndex used by the ParentRecipe check/fix (W111); when None, W111 is
    skipped. When `auto_fix` is set, a path-like ParentRecipe is rewritten to the
    parent's Identifier in place and reported under `fixed` instead of `issues`.
    """
    if not os.path.isfile(path):
        return [(1, "W100", "file not found; skipping")], []

    with open(path, encoding="utf-8", errors="replace") as handle:
        src = handle.read()

    if SKIP_MARKER in src:
        return [], []

    data, warning = parse_recipe(src)
    if warning is not None:
        return [(1, warning[0], warning[1])], []
    if not isinstance(data, dict):
        return [(1, "W102", "top-level of recipe is not a mapping; skipping")], []

    fixed = []
    parent_check_enabled = (
        "W111" not in disabled
        and recipe_index is not None
        and PARENT_RECIPE_MARKER not in src
    )

    # --- W111 auto-fix: rewrite a path-like ParentRecipe to the identifier, then
    # re-read/re-parse so the check below sees the corrected value (and does not
    # re-report it). ---
    if auto_fix and parent_check_enabled:
        fixed += maybe_fix_parent_recipe(path, data, recipe_index)
        if fixed:
            with open(path, encoding="utf-8", errors="replace") as handle:
                src = handle.read()
            data, _ = parse_recipe(src)
            if not isinstance(data, dict):
                return [], fixed

    source_lines = src.splitlines()
    issues = []

    if "W110" not in disabled and IDENTIFIER_NAME_MARKER not in src:
        issues += check_identifier_references_name(data, source_lines, exact)

    if parent_check_enabled:
        issues += check_parent_recipe_resolvable(
            data, source_lines, recipe_index.identifiers
        )

    return sorted(issues), fixed


def is_recipe_file(path):
    """True if `path` has one of the recognized recipe extensions."""
    return path.endswith(RECIPE_EXTENSIONS)


def check_files(
    paths, strict=False, exact=False, disabled=frozenset(), auto_fix=False, root="."
):
    """Check several recipe files; return a list of (path, issues, fixed) tuples.

    Non-recipe paths are skipped. Disabled codes are filtered from the results.
    The repo-wide RecipeIndex (for the ParentRecipe check/fix) is built once here
    from `root`, unless W111 is disabled. This is the programmatic entry point:
    it does no printing, so other code can consume the structured results.
    `main()` wraps it to print and exit.
    """
    recipe_index = None
    if "W111" not in disabled:
        recipe_index = build_recipe_index(root)

    results = []
    for path in paths:
        if not is_recipe_file(path):
            continue
        issues, fixed = check_file(
            path,
            strict=strict,
            exact=exact,
            disabled=disabled,
            recipe_index=recipe_index,
            auto_fix=auto_fix,
        )
        issues = [item for item in issues if item[1] not in disabled]
        fixed = [item for item in fixed if item[1] not in disabled]
        results.append((path, issues, fixed))
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
        "--auto-fix",
        choices=["yes", "no"],
        default=None,
        help="rewrite a path-like ParentRecipe (W111) to the parent's Identifier "
        "in place (default: yes when files are given, no when auto-discovering)",
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

    # auto-fix defaults to yes for explicit files, no when auto-discovering; an
    # explicit --auto-fix always wins.
    discovering = not args.files
    if args.auto_fix is not None:
        auto_fix = args.auto_fix == "yes"
    else:
        auto_fix = not discovering
    paths = args.files if args.files else discover_recipe_files(".")

    warning_count = 0
    fix_count = 0
    for path, issues, fixed in check_files(
        paths,
        strict=args.strict,
        exact=args.exact,
        disabled=disabled,
        auto_fix=auto_fix,
    ):
        for lineno, check_id, message in fixed:
            fix_count += 1
            print(f"{path}:{lineno}: [{check_id}] auto-fixed: {message}")
        for lineno, check_id, message in issues:
            warning_count += 1
            print(f"{path}:{lineno}: [{check_id}] warning: {message}")

    if fix_count:
        print(f"\nauto-fixed {fix_count} issue(s); review and re-stage the changes.")
    if warning_count:
        print(f"{warning_count} recipe-convention warning(s).")
    # a fix always fails the hook (so the changes are reviewed and re-staged);
    # warnings fail only under --strict
    return 1 if (fix_count or (warning_count and args.strict)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
