# workbuddy-skill-pack

[![Validate skill](https://github.com/lql341/workbuddy-skill-pack/actions/workflows/validate.yml/badge.svg)](https://github.com/lql341/workbuddy-skill-pack/actions/workflows/validate.yml)

Package and validate any agent skill directory into a `.zip` that WorkBuddy (Tencent CodeBuddy's
AI agent app) and the SkillHub publisher accept — and explain the rejection when they don't.

It exists because the platform's rules are strict, unevenly documented, and fail late: uploads
are rejected after the fact for nesting one directory too deep, for a missing `description`, or
for exceeding a 5 MiB cap, while other quirks (no icon, no guide questions) only show up after
installation.

```
skill: ./my-skill
zip:   /Users/you/Downloads/my-skill.zip (22925 bytes)
files: 48
result: OK
```

## Install

The repository *is* the skill: `SKILL.md` at the root, code under `skillpack/`, entrypoint under
`scripts/`. Link or copy it into any agent's skill directory.

```bash
# pi / Codex / Claude Code user-level skills
ln -s "$PWD" ~/.agents/skills/workbuddy-skill-pack

# plain CLI usage, no skill installation required
python3 scripts/pack.py --help
```

Requirements: Python 3.9+, macOS or Linux (Windows through WSL2). No third-party dependencies;
`pyyaml` is used automatically when present so SKILL.md frontmatter is parsed as real YAML,
otherwise a built-in minimal parser handles the standard forms.

## Usage

```bash
# validate only: no zip written, exit code 1 on any rule violation
python3 scripts/pack.py ./my-skill --check

# build ./out/<name>.zip, where <name> comes from SKILL.md frontmatter
python3 scripts/pack.py ./my-skill -o ./out

# explicit archive path
python3 scripts/pack.py ./my-skill -o ./out/my-skill.zip

# diagnose an archive that failed to upload
python3 scripts/pack.py ~/Downloads/my-skill.zip

# machine-readable output for CI
python3 scripts/pack.py ./my-skill -o ./out --json

# opt back into files excluded by default
python3 scripts/pack.py ./my-skill -o ./out --keep '*.slurm' --exclude 'drafts/*'

# packager version (CI and release workflows compare it with VERSION)
python3 scripts/pack.py --version
```

The archive is named after the `name` in SKILL.md frontmatter (not the folder), matching the
single root folder inside it. An invalid tree never produces a zip: the command exits 1 and lists
the offending paths.

## Rules enforced

| Rule | Detail |
|---|---|
| Layout | `<name>/SKILL.md`, at most one nested directory level: `skill/<dir>/<file>` |
| Frontmatter | YAML required; non-empty `name` and `description` |
| Size | 5 MiB cloud limit (4 MiB warning), checked uncompressed and as written |
| Excluded by default | `.git`, `.github`, `tests`, `.gitignore`, `.gitattributes`, `__pycache__`, `*.pyc`, `*.slurm`, `.DS_Store`, caches, `.env`/`*.key`/`*.pem` |
| Stripped install metadata | `_skillhub_meta.json`, `_marketplace_meta.json`, `_knot_meta.json`, `_builtin_market_meta.json`, `_user_meta.json` |
| Permissions | unix exec bits preserved; ZIP extra fields omitted, timestamps fixed |
| Post-build verification | reopen the archive: single root, `SKILL.md` present, depth, frontmatter, executable list |

Warnings cover the things users notice *after* import: missing `examples_zh`/`examples_en` (the
「试试这样用」 cards), non-slug names, folder/name mismatches, and frontmatter keys the client
ignores.

`references/packaging-rules.md` records the evidence behind each rule, the frontmatter field the
client actually reads, an error-text catalogue, and what a package *cannot* control (icons and
market-card fields are cloud asset properties, not zip content).

## Repository layout

```
workbuddy-skill-pack/
├── VERSION                     Synchronized SemVer release
├── CHANGELOG.md                Release history
├── SKILL.md                    Skill entrypoint: when to use it, rules, follow-up answers
├── agents/
│   └── openai.yaml             Codex UI metadata
├── skillpack/
│   ├── cli.py                  Argument parsing and dispatch
│   ├── frontmatter.py          YAML frontmatter reading (pyyaml or minimal fallback)
│   ├── packer.py               Source validation, zip building, archive verification
│   ├── report.py               Errors, warnings, and JSON/human rendering
│   ├── rules.py                Limits, exclusions, metadata files, depth check
│   └── version.py              VERSION lookup
├── scripts/
│   └── pack.py                 CLI entrypoint
├── references/
│   └── packaging-rules.md      Rule table, field table, error catalogue
└── tests/
    ├── test-pack.py            Packager, rule, and CLI regression tests
    └── test-release.py         VERSION / SKILL.md / CHANGELOG consistency
```

## Development

```bash
python3 -m py_compile scripts/*.py skillpack/*.py
python3 tests/test-pack.py
python3 tests/test-release.py
python3 scripts/pack.py . --check    # the repository must satisfy its own rules
```

CI runs the same four commands (`.github/workflows/validate.yml`). A green validation on `main`
creates the `v<version>` tag and GitHub release from `RELEASE_HIGHLIGHTS.md`, then attaches the
built `workbuddy-skill-pack.zip` asset (`.github/workflows/release.yml`).

Release steps: bump `VERSION`, set the same `version:` in `SKILL.md`, add a `## <version> -
<date>` section to `CHANGELOG.md`, refresh both `RELEASE_HIGHLIGHTS*.md` files, then merge to
`main`.

## License

MIT — see `LICENSE`.
