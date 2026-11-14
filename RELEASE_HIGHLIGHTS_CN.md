- 用 `scripts/pack.py` 把任意技能目录打成 WorkBuddy/SkillHub 可导入的 zip，也能给上传失败的包做体检。
- 提前拦住发布接口会拒的规则：`skill/<dir>/<file>` 层级、必需的 `name`/`description`、5 MiB 上限、
  安装元数据文件。
- 按导入器的视角复检成品，并对"装完才发现"的问题给出警告：缺引导问题、name 不规范、
  frontmatter 里有客户端不认识的键。
