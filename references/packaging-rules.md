# WorkBuddy skill packaging rules

Everything below was verified against the local WorkBuddy desktop client (app bundle
`/Applications/WorkBuddy.app/Contents/Resources/app.asar`) and the vendor docs:

- WorkBuddy《技能》: <https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills>
- CodeBuddy《Skills 技能系统》: <https://www.codebuddy.cn/docs/ide/Features/Skills>

## Layout

```
<skill-name>/                 zip root folder, name comes from SKILL.md frontmatter `name`
├── SKILL.md                  required
├── <dir>/<file>              at most ONE nested directory level
└── <file>                    root-level files are fine
```

Import routine facts (`resolveExtractedSkillRoot`): a zip is accepted when `SKILL.md` sits at
the archive root **or** inside a single top-level folder. Anything deeper than
`skill/<dir>/<file>` is rejected by the publishing API with
`目录层级超限 — Skill 包仅支持两级目录结构（根目录/二级目录/文件）`.

Consequence for code that ships Python packages: move `pkg/` up to the skill root and add the
skill root to `sys.path` in the entry script, instead of keeping `scripts/pkg/module.py`.

## Frontmatter

Required (`SKILL.md format is incorrect. Required fields: name, description`):

| key | notes |
|---|---|
| `name` | slug; also the installed folder name and zip folder name |
| `description` | single line; drives model invocation routing |

Recognized by the client parser (`asSkillFrontmatter`):

| key | effect |
|---|---|
| `display_name` / `displayName` | display name used by the local card |
| `description_zh` / `description_en` | localized description |
| `examples_zh` / `examples_en` | 「试试这样用」 guide questions (list, first 3 shown; also fed to skill intent matching) |
| `tags_zh` / `tags_en` | tags |
| `when-to-use` | extra routing text |
| `allowed-tools` | CSV or list |
| `disable`, `disable-model-invocation`, `user-invocable` | booleans |
| `license`, `version` | strings |
| `slug`, `summary`, `homepage` | used by the marketplace listing |

Ignored keys produce no error but no effect either; the packager warns about them.

## Size and content

- Cloud upload cap: **5 MiB** (`5242880` bytes, `createSkillCloudUploadSizeError`). The
  packager warns from 4 MiB.
- Absolute URLs for downloads are limited to `https://`.
- Unix exec bits are preserved; `scripts/*.sh` must stay 0755.
- Excluded by default: `.git`, `.github`, `tests`, `.gitignore`, `.gitattributes`,
  `__pycache__`, `*.pyc`, `*.slurm`, `.DS_Store`, caches, keys/`.env`.
- Stripped install metadata: `_skillhub_meta.json`, `_marketplace_meta.json`,
  `_knot_meta.json`, `_builtin_market_meta.json`, `_user_meta.json`
  (`packSkillDirToBlob` replaces them with a generated `_user_meta.json`).

## What the package CANNOT control

| UI element | where it comes from |
|---|---|
| Skill icon / cover | marketplace install only: `downloadSkillIconAndPersist` writes `_icon.png` from the remote `iconSource` and records `iconLocalPath` in the install meta. Shipping `_icon.png` inside a zip does nothing on import. |
| Chinese name, market summary, category, tags on the market card | cloud asset record, edited on the publishing console |
| Install/usage counts, author | cloud asset record |

Locally installed third-party skills (the 45 non-market entries in a typical
`~/.workbuddy/.skill-list-cache.json`) simply have `iconUrl: null` and render a default icon.

## Error catalogue → fix

| error text | cause | fix |
|---|---|---|
| `目录层级超限 — Skill 包仅支持两级目录结构` | `skill/a/b/file` | regroup to `skill/a/file` or `skill/file` |
| `SKILL.md not found in zip archive` | no SKILL.md at root or one folder down | repack with the folder layout above |
| `SKILL.md format is incorrect. Required fields: name, description` | missing/empty frontmatter keys | add both keys |
| `Skill package too large: N > 5242880` | over the cloud cap | drop docs/tests/binaries, prefer `references/` links |
| `A skill with name "x" already exists` | name collision | bump `name` or uninstall the old copy |
| `invalid_skill_name` | non-slug `name` | use `a-z0-9.-_` |

## Verification snippets

```bash
# layout + depth + size + frontmatter, without writing anything
python3 scripts/pack.py ./my-skill --check

# inspect a finished archive the way the importer would
python3 - <<'PY'
import re, yaml, zipfile
z = zipfile.ZipFile("my-skill.zip")
files = [n for n in z.namelist() if not n.endswith("/")]
print("max segments:", max(len(f.split("/")) for f in files))
fm = re.match(r"^---\n(.*?)\n---\n", z.read("my-skill/SKILL.md").decode(), re.S).group(1)
print({k: v for k, v in yaml.safe_load(fm).items() if k in ("name", "version", "examples_zh")})
PY
```
