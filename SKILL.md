---
name: workbuddy-skill-pack
description: Package and validate any agent skill directory into a WorkBuddy/SkillHub-importable .zip, enforcing the platform's directory-depth, SKILL.md frontmatter, size, and metadata-file rules.
slug: workbuddy-skill-pack
version: 0.1.1
summary: 把任意技能目录打包成 WorkBuddy 可导入的 zip，并校验层级/frontmatter/大小规则。
license: MIT
display_name: WorkBuddy 技能打包器
display_name_en: WorkBuddy Skill Packager
description_zh: 把任意技能目录打包成符合 WorkBuddy/SkillHub 导入规范的 zip，并校验目录层级、SKILL.md frontmatter、包大小和元数据文件。
description_en: Package any skill directory into a WorkBuddy/SkillHub-importable zip and validate depth, frontmatter, size, and metadata rules.
examples_zh:
  - 帮我把这个技能目录打成 WorkBuddy 技能包
  - 检查这个技能目录能不能上传到 WorkBuddy
  - 这个 zip 为什么上传报目录层级超限？
examples_en:
  - Package this skill directory for WorkBuddy
  - Check whether this skill directory will upload to WorkBuddy
  - Why does this zip fail with a directory-depth error?
---

# WorkBuddy Skill Packager

Turn a skill source directory into a `.zip` that WorkBuddy (and the CodeBuddy/SkillHub
importer) accepts, and explain any rejection before the user hits upload.

## When to use

- The user wants a WorkBuddy / SkillHub / CodeBuddy skill package from a repo or folder.
- Upload failed with `解析失败：目录层级超限`, `SKILL.md not found`, `Required fields: name,
  description`, or a size-limit error.
- The user asks why a skill's detail page shows no 「试试这样用」/ guide questions, no icon, or
  an English-only name after import.

## Usage

```bash
# validate only (no zip written)
python3 scripts/pack.py <skill-dir> --check

# build <out>/<name>.zip (name comes from SKILL.md frontmatter, not the folder name)
python3 scripts/pack.py <skill-dir> -o ~/Downloads

# explicit output path, extra excludes, machine-readable summary
python3 scripts/pack.py <skill-dir> -o ~/Downloads/my-skill.zip --exclude 'drafts/*' --json

# diagnose an archive that already failed to upload
python3 scripts/pack.py <path>/my-skill.zip
```

Exit code 0 = package valid, 1 = a rule failed (the report names the rule and the offending
paths). An invalid tree never produces an archive. Always report the failing rule verbatim to the
user instead of hand-waving.

## Rules the packager enforces

1. `SKILL.md` at the skill root; YAML frontmatter required.
2. `name` and `description` are mandatory, non-empty.
3. **At most two path segments inside the skill root**: `skill/<dir>/<file>`. A Python package
   at `scripts/my_pkg/mod.py` is rejected — move packages up to `skill/my_pkg/mod.py` and put
   the skill root on `sys.path` in the entry script.
4. Package ≤ 5 MiB (cloud upload limit), warning threshold at 4 MiB.
5. Dev/CI artifacts are excluded by default: `.git`, `.github`, `tests`, `.gitignore`,
   `.gitattributes`, `__pycache__`, `*.pyc`, `*.slurm`, `.DS_Store`, caches.
6. Install-metadata files are stripped: `_skillhub_meta.json`, `_marketplace_meta.json`,
   `_knot_meta.json`, `_builtin_market_meta.json`, `_user_meta.json`. The client replaces them
   on import, so shipping them only creates confusion (or false "market-installed" state).
7. Unix exec bits are preserved (`scripts/*.sh` must stay 0755); ZIP extra fields are omitted
   for reproducibility.

Details, evidence pointers, and the full frontmatter field table live in
`references/packaging-rules.md`.

## Answering the follow-up questions

- **No 「试试这样用」 cards** → add `examples_zh:` / `examples_en:` YAML lists to SKILL.md
  frontmatter (UI shows the first 3, clicking one fills the prompt).
- **No icon** → the local importer never reads an icon file. Icons only come from a
  marketplace/SkillHub install, where the client downloads `iconSource` into `_icon.png` and
  records `iconLocalPath` in the install meta. Do not promise `_icon.png` in the zip fixes it.
- **Chinese name / summary missing in the market card** → those are cloud asset fields set when
  publishing; `display_name`/`description_zh` in frontmatter only feed the local card.
- **Upload rejected for depth** → regroup nested packages as described in rule 3, then rebuild;
  never flatten by renaming modules (`from pkg.mod` imports would break).

## Files

- `scripts/pack.py` — CLI entrypoint (adds the repository root to `sys.path`, then calls
  `skillpack.cli.main`).
- `skillpack/` — `rules.py` (limits, exclusions, depth check), `frontmatter.py` (YAML reading with
  a minimal fallback), `packer.py` (validation, zip building, archive verification), `report.py`
  (errors/warnings/rendering), `cli.py`, `version.py`.
- `references/packaging-rules.md` — auditable rule page: observable behaviour, original error
  text, and a reproduce-it command per rule; recognized frontmatter keys; error catalogue; a dated
  traceability appendix for internal client symbol names.
- `tests/test-pack.py`, `tests/test-release.py` — `python3 tests/test-pack.py` before trusting a
  change; run `python3 scripts/pack.py . --check` so the repository keeps satisfying its own rules.
