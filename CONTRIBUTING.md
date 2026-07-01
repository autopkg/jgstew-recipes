# Contributing

Thanks for contributing to jgstew-recipes. This document covers the repository
layout, how to set up a development environment, how changes are validated, and
the conventions that custom processors are expected to follow.

## Cross-platform support

Unlike most AutoPkg recipe repos - which target macOS only - the processors and
recipes here are generally intended to run on **macOS, Windows, and Linux**.

What this means in practice:

- Recipes are written in **YAML** (rather than plist) for better cross-platform
  authoring, which is why AutoPkg 2.3+ is required.
- Processors should avoid macOS-only assumptions (paths, shell tools, frameworks)
  unless the processor is inherently platform-specific. Prefer cross-platform
  Python and tooling, and guard or feature-detect anything platform-specific.
- Platform-specific recipes and processors do exist as **exceptions** and are
  named/scoped accordingly - e.g. the `-Win`, `-Mac`, `-Linux` suffixes on recipe
  names (`Firefox-Win.download`, `Firefox-Mac.download`, `Firefox-Linux.download`),
  Windows-only MSI handling, or macOS-only DMG/pkg steps.

Because of this cross-platform goal, **some conventions here differ from
macOS-only AutoPkg recipe repos.** If a convention in this repo looks different
from what you have seen elsewhere, it is usually intentional and driven by the
need to also work on Windows and Linux - follow the conventions in this document
and the `autopkg_processor_check_conventions.py` hook rather than the macOS-only
norms.

## Repository layout

- `SharedProcessors/` - custom AutoPkg processors (Python). One class per file,
  class name == filename.
- `SharedDangerousProcessors/` - processors that run arbitrary code; intentionally
  excluded from the recipe schemas and treated separately. Do not add these to the
  schemas.
- `Test-Recipes/` - one test recipe per processor; the primary way processors are
  exercised in CI.
- `Recipes-Examples/` - example/demo recipes.
- `<Vendor>/` (e.g. `Mozilla/`, `Microsoft/`) - real download / pkg / bigfix /
  install recipes.
- `_Shared/` - shared parent recipes.
- `autopkg_processor_check_conventions.py` - opinionated pre-commit hook that
  checks (and auto-fixes) processor conventions. It is self-documenting: read its
  module docstring for the full list of checks (E0xx / W0xx codes).
- `.AutoPkgRecipeOpinionated.schema.json` - recipe schema used by the
  `check-jsonschema` pre-commit hook; restricts processors to a known allowlist.
- `.AutoPkgRecipe.schema.json` - non-opinionated variant; same structure but
  accepts any processor name (its built-in enum is suggestions only).

## Development setup

```sh
pip3 install --requirement requirements.txt   # processor dependencies
pip3 install pre-commit                        # if not already installed
pre-commit install                             # run the hooks on every commit
```

AutoPkg itself is expected to be checked out adjacent to this repo at
`../autopkg/Code` (the same path the README and CI use).

Environment notes: a fresh clone has **no `.venv`** - use `python3` directly. The
system `python3` may not have every module (e.g. `pyyaml`); install
`requirements.txt` as above.

## Validating changes

Everything is enforced by pre-commit. Run this before opening a PR:

```sh
pre-commit run --all-files        # all hooks
```

Useful targeted commands:

```sh
# processor conventions (auto-fixes shebang, header comment, docstrings,
# __all__, __main__ guard, print -> self.output, and more)
python3 autopkg_processor_check_conventions.py --auto-fix=yes SharedProcessors/*.py
#   --auto-fix=no       report only, do not modify files
#   --disable E005,E020 skip specific checks

./test_processors_load.sh         # imports every processor to confirm it loads
```

Prefer running the convention checker over hand-editing - it auto-fixes most of
the conventions below.

## Processor conventions

Every file in `SharedProcessors/` is expected to have:

- shebang `#!/usr/local/autopkg/python`
- a `# Created <year> by <author>` header comment
- a module docstring `"""See docstring for <Class> class"""`
- `__all__ = ["<Class>"]`
- a class named after the file, subclassing an AutoPkg `Processor` base
- a **substantial class docstring** - it is the processor's user-facing
  documentation, surfaced as the AutoPkg description via `description = __doc__`
  (use `description = __doc__`, never the reverse `__doc__ = description`)
- `input_variables` / `output_variables` as dict literals; every input needs a
  `description` (and `required`); every output needs a `description`
- a `main()` method whose docstring is `"""Execution starts here."""`
- a `__main__` guard exactly: `PROCESSOR = <Class>()` then
  `PROCESSOR.execute_shell()`
- `self.output(...)` for logging - never `print(...)`

## Conventions and gotchas

- **All files must be ASCII** (`verify-files-are-ascii` hook). Write emoji or
  symbols as `\u` escapes in source, not as literal characters.
- **Every processor needs a test recipe** in `Test-Recipes/` named after it
  (`<Name>.test.recipe.yaml`, or a `<Name>-Win.test.recipe.yaml` variant); missing
  ones are warned (W005).
- **Undeclared outputs**: writing `self.env["key"] = ...` for a key that is not an
  `output_variable` is warned (W004). For values that are intentionally not
  declared (very large strings, internal state), add `# output-undeclared-ok` on
  the write line.
- **Line-level opt-out markers** for the warnings that support them (place the
  marker on the flagged line or the line directly above it):
  - `# output-undeclared-ok` - undeclared `self.env` write (W004)
  - `# platform-specific-ok` - a guarded platform-specific import, e.g. `msilib` (W006)
  - `# input-unread-ok` - an input_variable declared but not read here (W007)
  - `# hardcoded-path-ok` - a deliberate user/machine-specific path (W008)
- **Other warnings**: W007 flags input_variables declared but never read from
  self.env (dead inputs); W008 flags hardcoded user/machine-specific paths (home
  dirs, per-user temp) - use cross-platform tool discovery instead.
- **Credentials and very large strings** (e.g. `BES_PASSWORD`, `file_base64`,
  `content_string`) are intentionally **not** declared as `output_variables`.
- **Recipe schemas**: `.AutoPkgRecipe*.schema.json` carry a list of built-in
  AutoPkg processors synced to a specific release (currently v2.9.0), kept
  deliberately inclusive. Keep both schema files' built-in enums in sync, and
  prefer allowing too much over rejecting a valid processor.
- Branch off `main`; do not commit directly to `main`.
