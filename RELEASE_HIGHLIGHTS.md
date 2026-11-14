- Build a WorkBuddy/SkillHub skill zip from any directory with `scripts/pack.py`, or diagnose an
  existing archive that failed to upload.
- Fail early on the rules the publishing API enforces: `skill/<dir>/<file>` depth, required
  `name`/`description`, the 5 MiB cloud limit, and install-metadata files.
- Verify the finished archive the way the importer does, and warn about the post-install
  surprises: missing guide questions, non-slug names, ignored frontmatter keys.
