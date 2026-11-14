# workbuddy-skill-pack

[![Validate skill](https://github.com/lql341/workbuddy-skill-pack/actions/workflows/validate.yml/badge.svg)](https://github.com/lql341/workbuddy-skill-pack/actions/workflows/validate.yml)

把任意 agent 技能目录打包成 WorkBuddy（腾讯 CodeBuddy 的 AI Agent 办公工具）和 SkillHub 发布
流程都能接受的 `.zip`，并在上传被拒之前把原因说清楚。

做这个工具的原因：平台规则严格、文档不全、报错总是在事后 —— 目录多嵌套一层、缺 `description`、
超 5 MiB，都是上传时才失败；而"没有图标""没有引导问题"这类问题要装完才发现。

```
skill: ./my-skill
zip:   /Users/you/Downloads/my-skill.zip (22925 bytes)
files: 48
result: OK
```

## 安装

仓库本身就是技能：`SKILL.md` 在根目录，代码在 `skillpack/`，入口在 `scripts/`。软链或复制到任意
agent 的技能目录即可。

```bash
# pi / Codex / Claude Code 用户级技能目录
ln -s "$PWD" ~/.agents/skills/workbuddy-skill-pack

# 只当命令行工具用，无需安装技能
python3 scripts/pack.py --help
```

要求 Python 3.9+，macOS 或 Linux（Windows 走 WSL2）。无第三方依赖；装了 `pyyaml` 时自动用它
按真正的 YAML 解析 frontmatter，否则用内置最小解析器。

## 用法

```bash
# 只校验，不写包；任何违规返回码 1
python3 scripts/pack.py ./my-skill --check

# 生成 ./out/<name>.zip，<name> 取自 SKILL.md frontmatter
python3 scripts/pack.py ./my-skill -o ./out

# 指定压缩包路径
python3 scripts/pack.py ./my-skill -o ./out/my-skill.zip

# 体检一个上传失败的包
python3 scripts/pack.py ~/Downloads/my-skill.zip

# CI 用机器可读输出
python3 scripts/pack.py ./my-skill -o ./out --json

# 把默认排除的文件重新纳入
python3 scripts/pack.py ./my-skill -o ./out --keep '*.slurm' --exclude 'drafts/*'

# 版本号（CI 与发布流程会和 VERSION 对齐）
python3 scripts/pack.py --version
```

压缩包名取自 SKILL.md frontmatter 的 `name`（不是目录名），与包内唯一的根目录一致。不合规的目录
不会产出任何 zip：命令返回 1 并列出具体路径。

## 强制规则

| 规则 | 细节 |
|---|---|
| 目录结构 | `<name>/SKILL.md`，最多一层子目录：`skill/<dir>/<file>` |
| frontmatter | 必须是 YAML，`name`、`description` 非空 |
| 大小 | 云端上限 5 MiB（4 MiB 起警告），未压缩与成品双重检查 |
| 默认排除 | `.git`、`.github`、`tests`、`.gitignore`、`.gitattributes`、`__pycache__`、`*.pyc`、`*.slurm`、`.DS_Store`、缓存、`.env`/`*.key`/`*.pem` |
| 剔除安装元数据 | `_skillhub_meta.json`、`_marketplace_meta.json`、`_knot_meta.json`、`_builtin_market_meta.json`、`_user_meta.json` |
| 权限 | 保留 unix 可执行位；不写 ZIP 扩展字段，时间戳固定（可复现） |
| 成品复检 | 重新打开压缩包：根目录唯一、`SKILL.md` 存在、层级、frontmatter、可执行文件清单 |

警告覆盖"装完才会发现"的问题：缺 `examples_zh`/`examples_en`（详情页没有「试试这样用」卡片）、
`name` 不是 slug、目录名与 name 不一致、客户端不认识的 frontmatter 键。

`references/packaging-rules.md` 把每条规则做成可自行核对的形态：可观察行为、原始报错文案、复现命令，
客户端真正读取的 frontmatter 字段，报错对照表，以及**包内无法控制**的部分（图标、市场卡片的
名称/简介/分类都是云端资产属性）。客户端内部符号名只出现在带日期的追溯附录里，不作为证据。

## 仓库结构

```
workbuddy-skill-pack/
├── VERSION                     同步的 SemVer 版本
├── CHANGELOG.md                版本历史
├── SKILL.md                    技能入口：何时用、规则、追问怎么答
├── agents/
│   └── openai.yaml             Codex 界面元数据
├── skillpack/
│   ├── cli.py                  参数解析与调度
│   ├── frontmatter.py          frontmatter 读取（pyyaml 或最小回退实现）
│   ├── packer.py               源校验、打包、成品复检
│   ├── report.py               错误/警告收集与 JSON 或人类可读输出
│   ├── rules.py                限制、排除规则、元数据文件名、层级检查
│   └── version.py              VERSION 读取
├── scripts/
│   └── pack.py                 命令行入口
├── references/
│   └── packaging-rules.md      规则表、字段表、报错对照表
└── tests/
    ├── test-pack.py            打包、规则、CLI 回归测试
    └── test-release.py         VERSION / SKILL.md / CHANGELOG 一致性
```

## 开发

```bash
python3 -m py_compile scripts/*.py skillpack/*.py
python3 tests/test-pack.py
python3 tests/test-release.py
python3 scripts/pack.py . --check    # 仓库本身必须满足自己的规则
```

CI 跑同样四条（`.github/workflows/validate.yml`）；`main` 上校验通过后，
`.github/workflows/release.yml` 会打 `v<version>` 标签、用 `RELEASE_HIGHLIGHTS.md` 建 Release，
并把打好的 `workbuddy-skill-pack.zip` 作为附件上传。

发版步骤：改 `VERSION`，同步 `SKILL.md` 里的 `version:`，在 `CHANGELOG.md` 加
`## <version> - <date>`，更新两个 `RELEASE_HIGHLIGHTS*.md`，然后合入 `main`。

## 许可证

MIT，见 `LICENSE`。
