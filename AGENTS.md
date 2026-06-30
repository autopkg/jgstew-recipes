# AGENTS.md

Guidance for AI agents working in this repo. See `README.md` for install/runtime
requirements (Python modules, AutoPkg repos, Docker).

## What this is

An AutoPkg recipe repository (`autopkg/jgstew-recipes`). Recipes are written in
**YAML** (requires AutoPkg 2.3+) and live in per-vendor folders (e.g. `Mozilla/`,
`Microsoft/`). Custom processors live in `SharedProcessors/`.

## Layout

- `SharedProcessors/` - custom AutoPkg processors (Python). One class per file,
  class name == filename.
- `SharedDangerousProcessors/` - processors that run arbitrary code; intentionally
  excluded from the recipe schemas and treated separately. Don't add these to schemas.
- `Test-Recipes/` - one test recipe per processor; the primary way processors are
  exercised in CI.
- `Recipes-Examples/` - example/demo recipes.
- `<Vendor>/` - real download / pkg / bigfix / install recipes.
- `_Shared/` - shared parent recipes.
- `autopkg_processor_check_conventions.py` - opinionated pre-commit hook that
  checks (and auto-fixes) processor conventions. It is self-documenting: read its
  module docstring for the full list of checks (E0xx / W0xx codes).
- `.AutoPkgRecipeOpinionated.schema.json` - recipe schema used by pre-commit
  (`check-jsonschema`); restricts processors to a known allowlist.
- `.AutoPkgRecipe.schema.json` - non-opinionated variant; same structure but
  accepts any processor name (the built-in enum is suggestions only).

## Validating changes

Everything is enforced by pre-commit. Run before considering work done:

```sh
pre-commit run --all-files        # all hooks
```

Targeted checks:

```sh
# processor conventions (auto-fixes shebang, docstrings, __all__, guard, etc.)
python3 autopkg_processor_check_conventions.py --auto-fix=yes SharedProcessors/*.py
# skip specific checks: --disable E005,E020
# report only:         --auto-fix=no

./test_processors_load.sh         # imports every processor to confirm it loads
```

Notes on the environment: a fresh clone has **no `.venv`** - use `python3`. The
system `python3` may lack `pyyaml`. AutoPkg itself is expected adjacent at
`../autopkg/Code` (see README).

## Processor conventions (enforced by the checker)

Every file in `SharedProcessors/` is expected to have:

- shebang `#!/usr/local/autopkg/python`
- `# Created <year> by <author>` header comment
- module docstring `"""See docstring for <Class> class"""`
- `__all__ = ["<Class>"]`
- a class named after the file, subclassing an AutoPkg `Processor` base
- a **substantial class docstring** - it is the processor's user-facing
  documentation, surfaced as the AutoPkg description via `description = __doc__`
  (use `description = __doc__`, never `__doc__ = description`)
- `input_variables` / `output_variables` as dict literals; every input needs a
  `description` (and `required`); every output needs a `description`
- a `main()` method with docstring `"""Execution starts here."""`
- a `__main__` guard exactly: `PROCESSOR = <Class>()` then `PROCESSOR.execute_shell()`
- `self.output(...)` for logging - never `print(...)`

Most of the above is auto-fixed by the checker; run it rather than hand-editing.

## Gotchas

- **Files must be ASCII** (`verify-files-are-ascii` hook). Write emoji/symbols as
  `\u` escapes in source, not literal characters.
- **Undeclared outputs**: a `self.env["key"] = ...` whose key isn't an
  `output_variable` is warned (W004). For intentionally undeclared values (very
  large strings, internal state), put `# output-undeclared-ok` on the write line.
- **Credentials & huge strings** (e.g. `BES_PASSWORD`, `file_base64`,
  `content_string`) are intentionally **not** declared as outputs.
- **Schema built-in enums**: `.AutoPkgRecipe*.schema.json` carry a list of
  built-in AutoPkg processors synced to a specific release (currently v2.9.0),
  kept deliberately inclusive. Keep both schema files' enums in sync, and prefer
  allowing too much over rejecting a valid processor.
- **Don't commit/push unless asked.** Branch off `main` for changes.
