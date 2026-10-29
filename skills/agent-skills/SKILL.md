---
name: agent-skills
description: >
  Agent Skills documentation and best practices. Use when the user asks to
  create, edit, review, or debug a "skill" — including the SKILL.md format,
  activation mechanism, description optimization, test cases, context
  efficiency, and bundling scripts. Also use when the user asks about the
  Agent Skills specification or skill creation workflow.
---

# Agent Skills

This skill documents the Agent Skills system — the standardized mechanism by
which coding agents load structured, domain-specific instructions.

## Documentation

The Agent Skills docs live in the official repository of the specification and
are not vendored here. Fetch them with `ketch scrape` (or `gh repo clone
agentskills/agentskills` for a local copy).

Base URL: `https://github.com/agentskills/agentskills/blob/main`

- **General**: `docs/`
  - `home.mdx` — overview of Agent Skills
  - `specification.mdx` — complete SKILL.md format
- **Skill Creation**: `docs/skill-creation/`
  - `quickstart.mdx` — Create your first skill, overview of format and
    activation
  - `best-practices.mdx` — Scoping, context efficiency, prescriptiveness,
    gotchas
  - `evaluating-skills.mdx` — Eval-driven iteration with test cases and grading
  - `optimizing-descriptions.mdx` — Testing and improving description triggering
  - `using-scripts.mdx` — Running commands and bundling scripts in skills

Read the most relevant docs for your current task first, and refer to the others
as needed.

## Maturity banner

Skills that can be silently wrong (parsers, extractors, tools with a moving API)
open with a `> **Status: work in progress.**` blockquote naming 2–3 concrete
failure modes and telling the agent to stop, report, and fix the skill before
resuming. Skip it for procedure skills. Keep line 1 verbatim so
`grep -rl 'Status: work in progress' skills/` finds unfinished ones, and swap the
banner for `## Known limits` once N clean tasks accumulate. Example: `pdf-tools`.
