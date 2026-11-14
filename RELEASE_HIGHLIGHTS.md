- New `--layout workbuddy`: flatten nested Python packages in the archive only, so a repository
  that keeps `scripts/<pkg>/…` can still produce an uploadable package without restructuring.
- The adapted tree is staged and `py_compile`d before zipping; collisions and residual depth stay
  fatal, the source tree is untouched, and the report states what changed.
