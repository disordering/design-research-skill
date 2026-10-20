# 可提交审查成果

该目录保存经过验收、计划进入 Git 的审查成果。开发阶段的临时运行放在 `out/stages/`，该目录不会提交。

## 命名约定

```text
deliverables/<YYYY-MM-DD>-<case-slug>/
  README.md
  review-metadata.json
  report-showcase.md
  report.json
  manifest.json
  screenshot.png
  prototype.png
  ...process files
  raw/
```

- 日期使用审查执行日期。
- `case-slug` 使用简短英文 kebab-case。
- 当前 `run-id` 保存在 `manifest.json` 和 `review-metadata.json` 中。
- 已验收成果不得原地覆盖；重跑时使用新的案例版本目录，例如 `<日期>-<case-slug>-v2/`。

## 当前成果

- [角色试用页审查](./2026-10-21-character-trial/README.md)
