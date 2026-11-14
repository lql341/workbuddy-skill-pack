# WorkBuddy skill packaging rules

Every rule below can be re-checked by a reader: through the product's own behaviour, through local
state the desktop app keeps on disk, or through strings inside the shipped client bundle. Internal
function names are kept only in the [traceability appendix](#appendix-traceability) — they are
useful for tracking a change, but they are not something a reader can rely on across releases.

Reference client: **WorkBuddy 5.9.3** (macOS, `app.asar` from 2026-10-27). Vendor documentation:

- WorkBuddy 《技能》: <https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills>
- CodeBuddy 《Skills 技能系统》: <https://www.codebuddy.cn/docs/ide/Features/Skills>

## 1. Package layout

```
<skill-name>/                 one root folder, named after the frontmatter `name`
├── SKILL.md                  required
├── <dir>/<file>              at most ONE nested directory level
└── <file>                    root-level files are fine
```

**Why:** uploading `skill/scripts/my_pkg/mod.py` fails with

```
解析失败：目录层级超限 — Skill 包仅支持两级目录结构（根目录/二级目录/文件），请移除子目录嵌套
```

That message comes from the publishing API, not from the desktop bundle, so it cannot be grepped
locally — reproduce it by uploading any archive with a two-directories-deep path.

**How to verify:** build two archives from the same tree, one with `scripts/pkg/mod.py` and one
with `pkg/mod.py`, and upload both. Only the second is accepted. The vendor docs also show
`scripts/`, `references/`, `assets/` as the only bundled-resource folders — all one level deep.

**Consequence for code:** move packages up to the skill root (`skill/my_pkg/mod.py`) and put the
skill root on `sys.path` in the entry script, instead of keeping the package under `scripts/`.
This repository does exactly that: `scripts/pack.py` is a thin entrypoint, `skillpack/` sits at
the root.

## 2. SKILL.md frontmatter

### Required

| key | notes |
|---|---|
| `name` | slug; also becomes the installed folder name and the zip root folder |
| `description` | single line; drives model-invocation routing |

Missing or empty values are rejected with one of:

```
SKILL.md format is incorrect. Required fields: name, description
SKILL.md format is incorrect. Required field "name" is missing.
SKILL.md format is incorrect. Required field "description" is missing.
```

**How to verify:** delete `description` from a known-good SKILL.md, upload, and read the error.

### Recognized fields

| key | observable effect |
|---|---|
| `display_name` / `displayName` | display name on the local skill card |
| `description_zh` / `description_en` | localized description on the local card |
| `examples_zh` / `examples_en` | the 「试试这样用」 cards (`Try it like this`); first 3 shown, clicking one fills the prompt; the same strings are also fed to skill intent matching |
| `tags_zh` / `tags_en` | tags |
| `when-to-use` | extra routing text |
| `allowed-tools` | CSV string or list |
| `disable`, `disable-model-invocation`, `user-invocable` | booleans |
| `license`, `version` | strings |
| `slug`, `summary`, `homepage` | marketplace listing fields |

Keys outside this list are ignored — no error, no effect. The packager warns about them.

**How to verify the guide questions:** install a skill whose SKILL.md has

```yaml
examples_zh:
  - 第一条引导问题
  - 第二条引导问题
```

Open its detail page: the section title is 「试试这样用」 and exactly those prompts appear as cards.
Remove the key, reinstall, and the section disappears.

## 3. Size and content

- Upload cap: **5 MiB (5242880 bytes)**. Exceeding it produces
  `Skill package exceeds the 5.00MB upload limit (actual X.XXMB)` or
  `Skill package too large: N > 5242880 bytes`. The packager warns from 4 MiB.
- Downloads during install must use `https://` URLs.
- Unix exec bits are preserved; `scripts/*.sh` must stay 0755 for shell entrypoints to run.
- Excluded by default: `.git`, `.github`, `tests`, `.gitignore`, `.gitattributes`, `__pycache__`,
  `*.pyc`, `*.slurm`, `.DS_Store`, caches, `.env` and key material.
- Stripped install metadata: `_skillhub_meta.json`, `_marketplace_meta.json`, `_knot_meta.json`,
  `_builtin_market_meta.json`, `_user_meta.json`. The client regenerates its own meta on import,
  so shipping them only creates a false "installed from the market" state — and the client's own
  export path replaces them with a generated `_user_meta.json`.

**How to verify:** create a 6 MiB archive and upload it; then install a package that contains
`_skillhub_meta.json` and look at the generated `~/.workbuddy/skills/<name>/` — the file is not
carried over as authored.

## 4. What the package cannot control

| UI element | where it actually comes from |
|---|---|
| Skill icon / cover | marketplace install only: the client downloads the remote `iconSource` into `_icon.png` next to the skill and records `iconLocalPath` in the install meta. **A `_icon.png` inside a zip does nothing on import.** |
| Chinese name, market summary, category, tags on the market card | cloud asset record, edited on the publishing console |
| Install/usage counts, author | cloud asset record |

**How to verify:** on a machine with WorkBuddy installed,

```bash
python3 - <<'PY'
import json, pathlib
cache = pathlib.Path.home() / ".workbuddy/.skill-list-cache.json"
skills = json.loads(cache.read_text())["results"]
local = [s for s in skills if s.get("source") == "userSettings"]
print("installed:", len(skills), "| locally imported:", len(local),
      "| locally imported with an icon:", sum(1 for s in local if s.get("iconUrl")))
PY
```

Locally imported skills report `iconUrl: null` (default icon), and only marketplace-installed
skills have a `local-file://…/_icon.png` URL plus a `_skillhub_meta.json` in their folder.

## 5. Error catalogue → fix

| error text | cause | fix |
|---|---|---|
| `目录层级超限 — Skill 包仅支持两级目录结构` | `skill/a/b/file` | regroup to `skill/a/file` or `skill/file` |
| `SKILL.md not found in zip archive` | no SKILL.md at the archive root or one folder down | repack with the folder layout above |
| `SKILL.md format is incorrect. Required fields: name, description` | missing/empty frontmatter keys | add both keys |
| `Skill package too large: N > 5242880` | over the cloud cap | drop docs/tests/binaries; keep long material in `references/` |
| `A skill with name "x" already exists` | name collision | bump `name` or uninstall the old copy |
| `invalid_skill_name` | non-slug `name` | use `a-z0-9.-_` |

## 6. Verify it yourself

```bash
# layout, depth, size, and frontmatter, without writing anything
python3 scripts/pack.py <skill-dir> --check

# inspect a finished archive the way the importer reads it
python3 - <<'PY'
import re, zipfile
from pathlib import Path
archive = Path("my-skill.zip")
with zipfile.ZipFile(archive) as z:
    names = [n for n in z.namelist() if not n.endswith("/")]
    print("files:", len(names))
    print("max segments:", max(len(n.split("/")) for n in names))
    print("roots:", {n.split("/")[0] for n in names})
    skill = z.read(f"{names[0].split('/')[0]}/SKILL.md").decode()
    print(re.match(r"^---\n(.*?)\n---\n", skill, re.S).group(1))
PY

# client-side strings this document relies on (macOS; adjust the path per platform)
python3 - <<'PY'
from pathlib import Path
asar = Path("/Applications/WorkBuddy.app/Contents/Resources/app.asar").read_bytes()
for needle in (b"var lt=5242880", b"Skill package too large",
               b"SKILL.md not found in zip archive",
               b'Required field "name" is missing',
               b"skills.detail.examples.title"):
    print(f"{needle.decode():42} {asar.count(needle)}")
PY
# expected on 5.9.3: 1, 2, 3, 2, 8
```

A count of `0` does not invalidate a rule — the desktop bundle is minified and renamed on every
release. It means the exact string moved; the product behaviour and the API error text still hold.

## Appendix: traceability

Recorded from WorkBuddy **5.9.3** desktop (`app.asar`, 2026-10-27). Names are internal, minified,
and change between releases; they are listed so a future reader can locate the same code path, not
as a citation.

| behaviour | symbol / string in the bundle |
|---|---|
| upload cap and its error | `var lt=5242880`, `createSkillCloudUploadSizeError`, `Skill package exceeds the …` |
| zip import and root resolution | `resolveExtractedSkillRoot`, `SKILL.md not found in zip archive` |
| frontmatter parsing | `asSkillFrontmatter`, `parseSkillFileImpl`, `Required field "name" is missing.` |
| guide questions | `skills.detail.examples.title` (= `试试这样用` / `Try it like this`), `ExamplesSection` |
| icon download and meta | `downloadSkillIconAndPersist`, `iconLocalPath`, `_icon<ext>` |
| export strips install meta | `packSkillDirToBlob`, `_user_meta.json` |
| install meta filenames | `_skillhub_meta.json`, `_marketplace_meta.json`, `_knot_meta.json`, `_builtin_market_meta.json` |
