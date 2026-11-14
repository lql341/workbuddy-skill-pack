# Changelog

## 0.2.0 - 2026-11-14

- Add `--layout workbuddy`: build an uploadable archive from a repository that must keep nested
  Python packages (`scripts/<pkg>/…`). For the packaged copy it lifts each `dir/pkg/` containing
  `__init__.py` to the skill root and inserts a marked `sys.path` bootstrap into the files that
  import it, after any docstring and `__future__` import.
- Stage and `py_compile` the adapted tree before zipping, and abort when it does not compile.
- Keep the transform honest: the source tree is never modified, name collisions and residual
  `a/b/file` depth remain fatal errors, and the report lists exactly what was moved and patched
  with a warning that the archive differs from the repository.
- Add `layout.py` plus nine tests, including an end-to-end run of the extracted entrypoint and a
  check that the source tree is untouched.

## 0.1.1 - 2026-11-14

- Rewrite `references/packaging-rules.md` as a page a public reader can audit: each rule now states
  the observable behaviour, the exact error text, and a command that reproduces it (product
  behaviour, on-disk install state, or strings in the shipped client bundle).
- Move internal client symbol names out of the rule text into a traceability appendix, dated to
  WorkBuddy 5.9.3, with an explicit note that they are minified internals that move between
  releases and are not citations.

## 0.1.0 - 2026-11-14

- Add `scripts/pack.py`: build `<name>.zip` from any skill directory, with a single top-level
  folder, preserved unix exec bits, and deterministic timestamps.
- Validate the rules the WorkBuddy publishing API enforces: at most `skill/<dir>/<file>`
  directory depth, `SKILL.md` with `name` + `description`, 5 MiB cloud size limit, and the
  default exclusions for dev artifacts, caches, keys, and install metadatas
  (`_skillhub_meta.json`, `_marketplace_meta.json`, `_knot_meta.json`,
  `_builtin_market_meta.json`, `_user_meta.json`).
- Verify the finished archive the way the importer does: single root folder, `SKILL.md` inside
  it, depth, frontmatter, and executable file list.
- Warn about the details users hit after import: missing `examples_zh`/`examples_en`
  (no 「试试这样用」 cards), non-slug names, folder/name mismatches, and frontmatter keys the
  client ignores.
- Accept an existing `.zip` as the target so a failed upload can be diagnosed locally.
- Document the evidence trail in `references/packaging-rules.md`, including why the package
  cannot control the skill icon or the market card fields.
