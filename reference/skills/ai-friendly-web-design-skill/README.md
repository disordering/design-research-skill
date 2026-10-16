# AI-Friendly Web Design Skill

[中文说明](./README.zh-CN.md)

A skill for coding agents that build, review, and refactor Web UI that should be easier for humans, screen readers, browser automation, Playwright tests, and AI agents to understand and operate.

> Inspired by: [@karminski-牙医](https://weibo.com/2169039837/QxmP8bEIS) · Compiled by: [@ianho7](https://github.com/ianho7)

## What it does

This skill helps agents choose better semantic HTML, clearer state, more stable locators, and more reproducible URL patterns when working on frontend UI.

`SKILL.md` is the entry file. The files under `references/` are supporting material that should be read on demand, not all at once unless the task genuinely needs them.

The guidance is written for coding agents in general. The installer in this repo currently targets Claude Code style skill directories because that is the packaging format used here.

When used for review, the skill reports findings with severity levels: `🔴 High / 🟡 Medium / 🟢 Low`.

## When to use

Use it when you are:

- Designing a new UI flow, component, or form
- Implementing or refactoring frontend UI
- Reviewing existing UI for accessibility, operability, or automation issues
- Generating Playwright or browser automation tests
- Deciding semantic HTML, ARIA, locator, or URL state patterns

## Structure

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

- `SKILL.md` is the entry point.
- `references/` contains focused reference files for principles, semantics, locators, review output, and common component recipes.
- `component-recipes.md` is a Round 2-lite addition for high-frequency components. It is intentionally short and is not a full component encyclopedia.
- Scripts and assets are not included by design. The skill stays lightweight and relies on small, readable reference files instead.

## Installation note

This repository currently ships an installer for Claude Code compatible skill directories under `.claude/skills/`.

If you use another coding agent, reuse the same `SKILL.md` and `references/` content in that agent's preferred skill or prompt format instead of assuming the installer is universal.

Quick install:

```bash
# Global install to ~/.claude/skills/
npx ai-friendly-web-design-skill

# Local install to ./.claude/skills/ in the current project
npx ai-friendly-web-design-skill --local

# Overwrite an existing install
npx ai-friendly-web-design-skill --force
```

Manual install:

- Copy `skills/ai-friendly-web-design/` into your target skill directory.
- For Claude Code, that is usually `~/.claude/skills/` globally or `./.claude/skills/` inside a project.

Release:

```bash
# Preflight only
node ./scripts/release.mjs --check

# Bump patch, publish to npm, then push commit and tag
node ./scripts/release.mjs

# Bump minor
node ./scripts/release.mjs --bump minor

# Publish an exact version
node ./scripts/release.mjs --version 1.2.0

# Bump version and preview without npm publish
node ./scripts/release.mjs --no-npm-publish
```

If you prefer `npx`, this repo also exposes:

```bash
npx ai-friendly-web-design-release --check
```

## Usage Examples

Use this skill when you want to design, review, refactor, or test web UI that should be easy for humans, screen readers, browser automation, Playwright, and AI agents to understand and operate.

### Review a single component

```txt
Use the ai-friendly-web-design skill to review src/components/LoginForm.tsx.

Focus on semantic HTML, labels, readable error states, and stable locators.
Do not modify code yet. Return High and Medium issues only.
```

### Improve a form

```txt
Use the ai-friendly-web-design skill to improve this form component.

Make sure every field has a label, errors are readable, required states are clear, and the submit action is easy for Playwright and AI agents to locate.
Keep the visual design unchanged.
```

### Design a searchable table

```txt
Use the ai-friendly-web-design skill to design a searchable order table.

Include search, filters, sorting, pagination, loading state, empty state, error state, URL state, and stable locators for critical actions.
Start with an AI-operable UI plan before writing code.
```

### Review a folder

```txt
Use the ai-friendly-web-design skill to review src/components/forms/.

Focus on form labels, errors, required states, disabled states, submit behavior, and stable locators.
Do not rewrite components. Suggest minimal fixes.
```

### Refactor a modal

```txt
Use the ai-friendly-web-design skill to refactor src/components/ConfirmDialog.tsx.

Make it easier for keyboard users, screen readers, Playwright, and AI agents to operate.
Preserve the existing visual design and avoid broad rewrites.
```

### Generate Playwright tests

```text
Use the ai-friendly-web-design skill to generate Playwright tests for the checkout flow.

Prefer getByRole, getByLabel, and getByText.
Avoid CSS selectors.
Suggest stable locators only when user-facing locators are not enough.
```

### Project-level review

```txt
Use the ai-friendly-web-design skill to perform a lightweight review of src/.

Return only the top High and Medium issues.
Focus on blocked user tasks, inaccessible forms, hover-only actions, unreadable errors, missing URL state, and brittle selectors.
Do not modify code.
```

## Design principle

Keep the skill small and operational:

- Strong entry file
- Focused references
- Read only what the task needs
- No scripts or assets unless there is a clear maintenance reason later
- Component recipes that guide implementation and review without turning into a UI handbook
