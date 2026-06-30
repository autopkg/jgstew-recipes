# AGENTS.md

Guidance for AI agents working in this repo.

This is an AutoPkg recipe repository (`autopkg/jgstew-recipes`): YAML recipes in
per-vendor folders, with custom processors in `SharedProcessors/`.

**Read [CONTRIBUTING.md](CONTRIBUTING.md) first.** It is the source of truth for
the repository layout, development setup, how changes are validated, and the
processor conventions. [README.md](README.md) covers using the recipes. Do not
duplicate that content here - this file only adds agent-specific notes.

## Agent-specific notes

- **Validate before finishing**: run `pre-commit run --all-files` and make sure it
  passes (see CONTRIBUTING.md for targeted commands).
- **Don't hand-fix processor boilerplate**: run the convention checker
  `python3 autopkg_processor_check_conventions.py --auto-fix=yes SharedProcessors/*.py`
  - it auto-fixes most conventions. Read its module docstring for the check list.
- **Keep files ASCII** (`verify-files-are-ascii` hook): emit any non-ASCII as `\u`
  escapes, not literal characters. This is the most common way generated edits
  break CI here.
- **Keep the two schemas in sync**: the built-in processor enum in
  `.AutoPkgRecipe.schema.json` and `.AutoPkgRecipeOpinionated.schema.json` should
  match (see CONTRIBUTING.md).
- **Don't commit or push unless asked**; branch off `main` for changes.
