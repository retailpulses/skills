---
name: skill-creator
description: >
  Create new skills, modify existing skills, and measure skill performance.
  Covers the full lifecycle: scoping, writing SKILL.md with proper frontmatter
  and structure, running evals, benchmarking, optimizing descriptions, and
  troubleshooting. Use when users want to create a skill from scratch, edit or
  optimize an existing skill, run evals to test a skill, or improve skill
  triggering accuracy.
---

# Skill Creator

A skill for creating new skills and iteratively improving them through evaluation.

At a high level, the process of creating a skill goes like this:
- Decide what you want the skill to do and roughly how it should do it
- Write a draft of the skill
- Create test prompts and run the agent with the skill on them
- Evaluate the results both qualitatively and quantitatively
- Rewrite the skill based on feedback
- Repeat until satisfied
- Expand the test set and try again at larger scale

## Creating a Skill

### Step 1: Determine Scope

1. **Ask clarifying questions**:
   - What specific capability should this skill provide?
   - When should the agent use this skill?
   - What tools or resources does it need?
   - Is this for personal use or team sharing?

2. **Keep it focused**: One skill = one capability.
   - Good: "PDF form filling", "Excel data analysis"
   - Too broad: "Document processing", "Data tools"

### Step 2: Choose Skill Location

**Personal Skills** (user skill directory): Individual workflows, experiments, personal tools.

**Project Skills** (project skill directory): Team workflows, project-specific expertise, shared utilities (committed to git).

### Step 3: Create File Structure

```bash
mkdir -p .agents/skills/skill-name
```

For multi-file skills:
```
skill-name/
├── SKILL.md          (required)
├── agents/           (platform-specific agent configs)
├── scripts/          (helper scripts)
├── references/       (supplementary docs)
└── templates/        (file templates)
```

### Step 4: Write SKILL.md Frontmatter

Create YAML frontmatter:

```yaml
---
name: skill-name
description: Brief description of what this does and when to use it
---
```

**Field requirements:**

- **name**:
  - Lowercase letters, numbers, hyphens only
  - Max 64 characters
  - Must match directory name
  - Good: `pdf-processor`, `git-commit-helper`
  - Bad: `PDF_Processor`, `Git Commits!`

- **description**:
  - Max 1024 characters
  - Include BOTH what it does AND when to use it
  - Use specific trigger words users would say
  - Mention file types, operations, and context

**Optional frontmatter fields:**

- **allowed-tools**: Restrict tool access (comma-separated)
  ```yaml
  allowed-tools: Read, Grep, Glob
  ```

### Step 5: Write Effective Descriptions

The description is critical for skill discovery.

**Formula**: `[What it does] + [When to use it] + [Key triggers]`

✅ **Good**:
```yaml
description: Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
```

❌ **Too vague**:
```yaml
description: Helps with documents
description: For data analysis
```

**Tips**: Include specific file extensions (.pdf, .xlsx, .json), mention common user phrases ("analyze", "extract", "generate"), list concrete operations, add context clues ("Use when...", "For...").

### Step 6: Structure the Skill Content

Use clear Markdown sections:

```markdown
# Skill Name

Brief overview of what this skill does.

## Quick start
Provide a simple example to get started immediately.

## Instructions
Step-by-step guidance for the agent.

## Examples
Show concrete usage examples with code or commands.

## Best practices
Key conventions, common pitfalls, when to use vs. not use.

## Requirements
List any dependencies or prerequisites.
```

Reference supporting files from SKILL.md:
```markdown
For advanced usage, see [reference.md](reference.md).
Run the helper script: `python scripts/helper.py input.txt`
```

## Common Patterns

### Read-only Skill
```yaml
---
name: code-reader
description: Read and analyze code without making changes. Use for code review, understanding codebases, or documentation.
allowed-tools: Read, Grep, Glob
---
```

### Script-based Skill
```yaml
---
name: data-processor
description: Process CSV and JSON data files with Python scripts. Use when analyzing data files or transforming datasets.
---
```

### Multi-file Skill with Progressive Disclosure
Put advanced details in separate files; reference them from SKILL.md. Keep SKILL.md lean — detailed reference material in `references/`.

## Validation Checklist

Before finalizing a skill, verify:
- [ ] Name is lowercase, hyphens only, max 64 chars
- [ ] Description is specific and < 1024 chars
- [ ] Description includes "what" and "when"
- [ ] YAML frontmatter is valid (no tabs, proper indentation)
- [ ] Instructions are step-by-step and actionable
- [ ] Examples are concrete and realistic
- [ ] Dependencies are documented
- [ ] Skill activates on relevant queries

## Running and Evaluating Test Cases

1. Spawn all runs (with-skill AND baseline) in the same turn
2. Draft assertions while runs are in progress
3. Capture timing data as runs complete
4. Grade, aggregate, and launch the viewer
5. Read the feedback and improve

## Improving the Skill

1. Generalize from the feedback
2. Keep the prompt lean
3. Explain the why behind instructions
4. Look for repeated work across test cases

## Description Optimization

1. Generate trigger eval queries (20 queries — should-trigger and should-not-trigger)
2. Review with user
3. Run the optimization loop
4. Apply the result

## Troubleshooting

**Skill doesn't activate:**
- Make description more specific with trigger words
- Include file types and operations in description
- Add "Use when..." clause with user phrases

**Multiple skills conflict:**
- Make descriptions more distinct
- Use different trigger words
- Narrow the scope of each skill

**Skill has errors:**
- Check YAML syntax (no tabs, proper indentation)
- Verify file paths (use forward slashes)
- Ensure scripts have execute permissions
- List all dependencies

## Best Practices for Skill Authors

1. **One skill, one purpose**: Don't create mega-skills
2. **Specific descriptions**: Include trigger words users will say
3. **Clear instructions**: Write for the agent, not humans
4. **Concrete examples**: Show real code, not pseudocode
5. **List dependencies**: Mention required packages
6. **Test with teammates**: Verify activation and clarity
7. **Use progressive disclosure**: Put advanced details in separate files

## Reference Files

- `agents/grader.md` — How to evaluate assertions against outputs
- `agents/comparator.md` — How to do blind A/B comparison
- `agents/analyzer.md` — How to analyze results
- `references/schemas.md` — JSON structures
