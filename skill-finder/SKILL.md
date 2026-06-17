---
name: skill-finder
description: Find, search, recommend, and install agent skills from the internal catalog, skills.sh, ClawHub, and SkillsMP. Use when user asks to find, search, discover, or choose skills, or says "how do I do X", "find a skill for X", "is there a skill that can...", or expresses interest in extending capabilities.
always_apply: true
---

# Skill Finder

When a user asks to **find**, **search**, **discover**, or **install** agent skills, use this skill to search across platforms, evaluate results, and install the best match.

## Available Platforms

| Platform | Best For | Search Method |
|----------|----------|---------------|
| **Internal Catalog** | Official/first-party skills, already vetted | Local file read |
| **skills.sh** | Open-source, workflow automation | CLI: `npx skills find` |
| **ClawHub** | Community-driven, version management | CLI: `clawhub search` |
| **SkillsMP** | Largest database (283K+), AI semantic search | REST API |

## Decision Tree

### Step 1: Analyze User Query

**Specific platform requested:**
- "from internal" / "internal catalog" -> Internal Catalog only
- "from skills.sh" -> skills.sh only
- "from clawhub" -> ClawHub only
- "from skillsmp" -> SkillsMP only

**Otherwise -> ALWAYS start with Internal Catalog, then escalate if needed.**

### Step 2: Search Internal Skill Catalog (ALWAYS do this first)

Check locally installed skills and the internal catalog for matching skills by name or description. Look for skills that match the user's domain keywords.

### Step 3: Choose Search Strategy (External Platforms)

**Strategy A: Single Platform (Fast)**
1. Run `npx skills find <query>`
2. If a good match is found, install it directly

**Strategy B: Multi-Platform Search (Comprehensive)**
Search all three platforms in parallel:
- `npx skills find <query>`
- `clawhub search <query>`
- SkillsMP API search

**Strategy C: Retry with Alternative Keywords**
Try up to 3 times with different queries per platform. Use synonyms, broader/narrower terms. For example, if `npx skills find deploy` has no good match, try `npx skills find deployment` or `npx skills find ci-cd`.

**Pro Tip:** For specialized/niche queries (e.g., "arxiv papers", "quantum computing"), always check SkillsMP as it has the largest database.

### Step 4: Evaluate Results and Install

If a suitable skill is found, **pick the best match and install it directly** — do not ask the user for confirmation. Prefer official / most popular packages.

Install to the **current workspace** (committed with the project):

```bash
npx skills add <owner/repo@skill> -y
```

Do **NOT** use the `-g` flag — skills should be installed locally to the workspace.

After installation, briefly report what was installed and what it does. Provide the link to learn more at skills.sh.

### Step 5: If No Good Match

If after 3 attempts no suitable skill is found, **do not install anything**. Instead:
1. Acknowledge that no existing skill was found
2. Offer to help with the task directly using your general capabilities
3. Suggest the user could create their own skill with `npx skills init`

## Installation Guidelines

**Default: Install to the agent's own directory.**

Recommended methods:
1. `git clone` - Safest for single-skill repos
2. "Install + Move" - Best for monorepos: `npx skills add <repo> --skill <name> -y`
3. `clawhub install <slug> --force`
4. SkillsMP -> GitHub clone

## Common Skill Categories

When searching, consider these common categories:

| Category        | Example Queries                          |
| --------------- | ---------------------------------------- |
| Web Development | react, nextjs, typescript, css, tailwind |
| Testing         | testing, jest, playwright, e2e           |
| DevOps          | deploy, docker, kubernetes, ci-cd        |
| Documentation   | docs, readme, changelog, api-docs        |
| Code Quality    | review, lint, refactor, best-practices   |
| Design          | ui, ux, design-system, accessibility     |
| Productivity    | workflow, automation, git                |

## Tips for Effective Searches

1. **Use specific keywords**: "react testing" is better than just "testing"
2. **Try alternative terms**: If "deploy" doesn't work, try "deployment" or "ci-cd"
3. **Check popular sources**: Many skills come from `vercel-labs/agent-skills` or `ComposioHQ/awesome-claude-skills`

## Key Commands Reference

- `npx skills find [query]` - Search for skills interactively or by keyword
- `npx skills add <package>` - Install a skill from GitHub or other sources
- `npx skills check` - Check for skill updates
- `npx skills update` - Update all installed skills

**Browse skills at:** https://skills.sh/
