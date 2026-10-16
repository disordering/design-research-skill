# AI-Friendly Web Design Skill

[English README](./README.md)

这是一个面向 coding agents 的 skill，帮助你构建、审查和重构更容易被人类、屏幕阅读器、browser automation、Playwright 测试和 AI agent 理解与操作的 Web UI。

> 灵感来源：[@karminski-牙医](https://weibo.com/2169039837/QxmP8bEIS) · 整理者：[@ianho7](https://github.com/ianho7)

## 这个 skill 是做什么的

这个 skill 会帮助 agent 在处理前端 UI 时，优先选择更合适的 semantic HTML、更清晰的状态表达、更稳定的定位方式，以及更容易复现的 URL state。

`SKILL.md` 是入口文件。`references/` 目录下的文件是按需读取的补充材料，除非任务确实需要，否则不应该一次性全部读取。

这些指导原则本身是面向通用 coding agents 的。这个仓库里的安装器目前仍然面向 Claude Code 风格的 skill 目录，因为仓库现在采用的是这种打包方式。

用于 review 时，skill 会按严重程度输出问题：`🔴 High / 🟡 Medium / 🟢 Low`。

## 什么时候使用

适合这些场景：

- 设计新的 UI 流程、组件或表单
- 实现或重构前端 UI
- 审查现有 UI 的可访问性、可操作性或自动化兼容性
- 生成 Playwright 或 browser automation 测试
- 决定 semantic HTML、ARIA、locator 或 URL state 的实现方式

## 目录结构

```txt
skills/
  ai-friendly-web-design/
    SKILL.md
    references/
      principles.md
      semantic-html-first.md
      locator-and-state.md
      review-output-format.md
      component-recipes.md
```

- `SKILL.md` 是入口。
- `references/` 里是按主题拆分的参考材料，分别覆盖原则、语义结构、locator 与 URL state、review 输出格式，以及常见组件 recipes。
- `component-recipes.md` 是 Round 2-lite 新增的组件级参考，面向高频组件，刻意保持短小，不是完整组件百科。
- 当前不包含 scripts 和 assets，这是有意保持轻量的设计。

## 安装说明

当前仓库自带的安装器会把内容安装到 Claude Code 兼容的 `.claude/skills/` 目录。

如果你使用的是其他 coding agent，可以复用同一套 `SKILL.md` 和 `references/` 内容，但需要按目标 agent 的 skill 或 prompt 格式自行接入，不要默认认为这个安装器可直接通用。

快速安装：

```bash
# 全局安装到 ~/.claude/skills/
npx ai-friendly-web-design-skill

# 安装到当前项目的 ./.claude/skills/
npx ai-friendly-web-design-skill --local

# 覆盖已有安装
npx ai-friendly-web-design-skill --force
```

手动安装：

- 将 `skills/ai-friendly-web-design/` 复制到目标 skill 目录。
- 对 Claude Code 来说，通常是全局的 `~/.claude/skills/`，或者项目内的 `./.claude/skills/`。

发布：

```bash
# 仅做预检查
node ./scripts/release.mjs --check

# 升 patch 版本，发布到 npm，并 push commit/tag
node ./scripts/release.mjs

# 升 minor 版本
node ./scripts/release.mjs --bump minor

# 直接发布指定版本号
node ./scripts/release.mjs --version 1.2.0

# 升版本并预览，但不发布 npm
node ./scripts/release.mjs --no-npm-publish
```

如果你更习惯 `npx`，仓库也暴露了这个命令：

```bash
npx ai-friendly-web-design-release --check
```

## 使用示例

当你希望设计、审查、重构或测试一套更容易被人类、屏幕阅读器、browser automation、Playwright 和 AI agents 理解与操作的 Web UI 时，可以使用这个 skill。

### 审查单个组件

```txt
Use the ai-friendly-web-design skill to review src/components/LoginForm.tsx.

Focus on semantic HTML, labels, readable error states, and stable locators.
Do not modify code yet. Return High and Medium issues only.
```

### 改进一个表单

```txt
Use the ai-friendly-web-design skill to improve this form component.

Make sure every field has a label, errors are readable, required states are clear, and the submit action is easy for Playwright and AI agents to locate.
Keep the visual design unchanged.
```

### 设计一个可搜索表格

```txt
Use the ai-friendly-web-design skill to design a searchable order table.

Include search, filters, sorting, pagination, loading state, empty state, error state, URL state, and stable locators for critical actions.
Start with an AI-operable UI plan before writing code.
```

### 审查一个目录

```txt
Use the ai-friendly-web-design skill to review src/components/forms/.

Focus on form labels, errors, required states, disabled states, submit behavior, and stable locators.
Do not rewrite components. Suggest minimal fixes.
```

### 重构一个 modal

```txt
Use the ai-friendly-web-design skill to refactor src/components/ConfirmDialog.tsx.

Make it easier for keyboard users, screen readers, Playwright, and AI agents to operate.
Preserve the existing visual design and avoid broad rewrites.
```

### 生成 Playwright 测试

```txt
Use the ai-friendly-web-design skill to generate Playwright tests for the checkout flow.

Prefer getByRole, getByLabel, and getByText.
Avoid CSS selectors.
Suggest stable locators only when user-facing locators are not enough.
```

### 项目级轻量 review

```txt
Use the ai-friendly-web-design skill to perform a lightweight review of src/.

Return only the top High and Medium issues.
Focus on blocked user tasks, inaccessible forms, hover-only actions, unreadable errors, missing URL state, and brittle selectors.
Do not modify code.
```

## 设计原则

保持这个 skill 小而能用：

- 入口文件要强
- references 要聚焦
- 只读取当前任务需要的内容
- 没有明确维护理由前，不加入 scripts 或 assets
- 组件 recipes 只服务实现与 review，不发展成 UI 手册
